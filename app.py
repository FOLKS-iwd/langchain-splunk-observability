import logging

from flask import Flask, request, jsonify

from config import Config
from rag_engine import RAGEngine
from observability import LLMObserver
from splunk_logger import SplunkHECLogger

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# init components
splunk = SplunkHECLogger()
observer = LLMObserver(splunk_logger=splunk)
engine = RAGEngine(observer=observer)


def init_engine():
    """Load existing FAISS index or build from docs folder."""
    if engine.load_existing_index():
        logger.info("Loaded existing FAISS index")
    else:
        count = engine.load_documents()
        if count > 0:
            logger.info("Indexed %d chunks from documents", count)
        else:
            logger.warning("No documents indexed, queries will fail")


@app.route("/query", methods=["POST"])
def handle_query():
    data = request.get_json(silent=True)
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400

    with observer.track_latency() as timing:
        try:
            result = engine.query(question)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception as e:
            logger.exception("Unhandled error during query")
            return jsonify({"error": "Internal error"}), 500

    latency = timing.get("latency_ms", 0)

    # send the final aggregated observation
    engine.finalize_observation(question, result, timing)

    return jsonify({
        "answer": result["answer"],
        "metadata": {
            "latency_ms": latency,
            "tokens": result["token_usage"],
            "sources_count": result["source_documents_count"],
            "model": result["model_name"],
        },
    })


@app.route("/health", methods=["GET"])
def health():
    index_loaded = engine.vectorstore is not None
    return jsonify({
        "status": "ok" if index_loaded else "degraded",
        "index_loaded": index_loaded,
    })


@app.route("/stats", methods=["GET"])
def stats():
    return jsonify(observer.stats.to_dict())


if __name__ == "__main__":
    missing = Config.validate()
    if missing:
        logger.error("Missing env vars: %s", ", ".join(missing))
    else:
        init_engine()
        app.run(host="0.0.0.0", port=5000, debug=False)
