import os
import logging
from typing import Any

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.callbacks import get_openai_callback

from config import Config
from observability import LLMObserver

logger = logging.getLogger(__name__)


class RAGEngine:
    """RAG pipeline: load docs, embed in FAISS, query via RetrievalQA."""

    def __init__(self, observer: LLMObserver | None = None):
        self.observer = observer or LLMObserver()
        self.embeddings = OpenAIEmbeddings(openai_api_key=Config.OPENAI_API_KEY)
        self.llm = ChatOpenAI(
            model_name=Config.OPENAI_MODEL,
            openai_api_key=Config.OPENAI_API_KEY,
            temperature=0.2,
        )
        self.vectorstore: FAISS | None = None
        self.qa_chain: RetrievalQA | None = None

    def load_documents(self, docs_path: str | None = None) -> int:
        """Load and index text files from the docs folder."""
        path = docs_path or Config.DOCS_PATH
        if not os.path.isdir(path):
            logger.warning("Docs directory not found: %s", path)
            return 0

        loader = DirectoryLoader(
            path,
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        documents = loader.load()
        if not documents:
            logger.warning("No documents found in %s", path)
            return 0

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(documents)
        logger.info("Split %d documents into %d chunks", len(documents), len(chunks))

        self.vectorstore = FAISS.from_documents(chunks, self.embeddings)

        # persist to disk for reuse
        self.vectorstore.save_local(Config.FAISS_INDEX_PATH)

        self._build_chain()
        return len(chunks)

    def load_existing_index(self) -> bool:
        """Load a previously saved FAISS index."""
        if not os.path.isdir(Config.FAISS_INDEX_PATH):
            return False
        try:
            self.vectorstore = FAISS.load_local(
                Config.FAISS_INDEX_PATH,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            self._build_chain()
            return True
        except Exception as e:
            logger.error("Could not load existing index: %s", e)
            return False

    def _build_chain(self):
        if self.vectorstore is None:
            raise RuntimeError("Vectorstore not initialized")

        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 4},
        )
        self.qa_chain = RetrievalQA.from_chain_type(
            llm=self.llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
        )

    def query(self, question: str) -> dict[str, Any]:
        """Run a question through the RAG pipeline with full instrumentation."""
        if self.qa_chain is None:
            raise RuntimeError(
                "RAG engine not initialized. Call load_documents() first."
            )

        with self.observer.track_latency() as timing:
            try:
                with get_openai_callback() as cb:
                    result = self.qa_chain.invoke({"query": question})

                source_docs = result.get("source_documents", [])
                doc_count = len(source_docs)
                latency = timing.get("latency_ms", 0)

                # retrieval event
                self.observer.observe_retrieval(question, doc_count, latency)

                token_info = {
                    "prompt_tokens": cb.prompt_tokens,
                    "completion_tokens": cb.completion_tokens,
                    "total_tokens": cb.total_tokens,
                }

                query_result = {
                    "answer": result["result"],
                    "source_documents_count": doc_count,
                    "token_usage": token_info,
                    "model_name": Config.OPENAI_MODEL,
                }

                return query_result

            except Exception as e:
                latency = timing.get("latency_ms", 0)
                self.observer.observe_error(question, e, latency)
                raise

    def finalize_observation(self, question: str, result: dict, timing: dict):
        """Called after the context manager exits so latency is set."""
        latency = timing.get("latency_ms", 0)
        self.observer.observe_query(question, result, latency)
