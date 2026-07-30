import time
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from splunk_logger import SplunkHECLogger
from config import Config

logger = logging.getLogger(__name__)


@dataclass
class QueryStats:
    """In-memory stats tracking for the API."""

    total_queries: int = 0
    total_errors: int = 0
    total_latency_ms: float = 0.0
    total_tokens_used: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_queries, 2)

    @property
    def error_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return round(self.total_errors / self.total_queries, 4)

    def record_query(self, latency_ms: float, tokens: int, is_error: bool = False):
        with self._lock:
            self.total_queries += 1
            self.total_latency_ms += latency_ms
            self.total_tokens_used += tokens
            if is_error:
                self.total_errors += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "total_errors": self.total_errors,
            "avg_latency_ms": self.avg_latency_ms,
            "error_rate": self.error_rate,
            "total_tokens_used": self.total_tokens_used,
        }


class LLMObserver:
    """Instruments LangChain calls and ships telemetry to Splunk."""

    def __init__(self, splunk_logger: SplunkHECLogger | None = None):
        self.splunk = splunk_logger or SplunkHECLogger()
        self.stats = QueryStats()

    @contextmanager
    def track_latency(self) -> Generator[dict[str, float], None, None]:
        """Context manager that measures wall-clock time in milliseconds."""
        timing: dict[str, float] = {}
        start = time.perf_counter()
        try:
            yield timing
        finally:
            elapsed = (time.perf_counter() - start) * 1000
            timing["latency_ms"] = round(elapsed, 2)

    def observe_query(
        self,
        query_text: str,
        result: dict[str, Any],
        latency_ms: float,
    ) -> None:
        """Log a completed RAG query with all available metadata."""
        token_usage = result.get("token_usage", {})
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)
        total_tokens = token_usage.get("total_tokens", 0)
        doc_count = result.get("source_documents_count", 0)
        model_name = result.get("model_name", Config.OPENAI_MODEL)

        self.stats.record_query(latency_ms, total_tokens)

        self.splunk.log_query(
            query_text=query_text,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            source_documents_count=doc_count,
        )

    def observe_retrieval(
        self,
        query_text: str,
        doc_count: int,
        latency_ms: float,
    ) -> None:
        self.splunk.log_retrieval(query_text, doc_count, latency_ms)

    def observe_error(
        self,
        query_text: str,
        error: Exception,
        latency_ms: float = 0.0,
    ) -> None:
        self.stats.record_query(latency_ms, 0, is_error=True)
        self.splunk.log_error(
            query_text=query_text,
            error_message=str(error),
        )
        logger.error("Query failed for '%s': %s", query_text[:80], error)
