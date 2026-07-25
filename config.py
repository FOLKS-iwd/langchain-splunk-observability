import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration loaded from .env file."""

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    SPLUNK_HEC_URL: str = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088")
    SPLUNK_HEC_TOKEN: str = os.getenv("SPLUNK_HEC_TOKEN", "")
    SPLUNK_INDEX: str = os.getenv("SPLUNK_INDEX", "llm_observability")
    SPLUNK_SOURCETYPE: str = os.getenv("SPLUNK_SOURCETYPE", "langchain_events")

    FAISS_INDEX_PATH: str = os.getenv("FAISS_INDEX_PATH", "./faiss_store")
    DOCS_PATH: str = os.getenv("DOCS_PATH", "./docs")

    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls) -> list[str]:
        missing = []
        if not cls.OPENAI_API_KEY:
            missing.append("OPENAI_API_KEY")
        if not cls.SPLUNK_HEC_TOKEN:
            missing.append("SPLUNK_HEC_TOKEN")
        return missing
