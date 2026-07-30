import json
import time
import logging
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import Config

logger = logging.getLogger(__name__)


class SplunkHECLogger:
    """Ships structured events to Splunk via HTTP Event Collector."""

    def __init__(
        self,
        hec_url: Optional[str] = None,
        hec_token: Optional[str] = None,
        index: Optional[str] = None,
        sourcetype: Optional[str] = None,
        verify_ssl: bool = False,
    ):
        self.hec_url = (hec_url or Config.SPLUNK_HEC_URL).rstrip("/")
        self.hec_token = hec_token or Config.SPLUNK_HEC_TOKEN
        self.index = index or Config.SPLUNK_INDEX
        self.sourcetype = sourcetype or Config.SPLUNK_SOURCETYPE
        self.verify_ssl = verify_ssl

        self.session = self._build_session()
        self._event_endpoint = f"{self.hec_url}/services/collector/event"

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Splunk {self.hec_token}",
            "Content-Type": "application/json",
        })

        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _build_payload(self, event_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "time": event_data.get("timestamp", time.time()),
            "index": self.index,
            "sourcetype": self.sourcetype,
            "source": "langchain_rag",
            "event": event_data,
        }

    def send_event(self, event_data: dict[str, Any]) -> bool:
        """Send a single event to Splunk HEC. Returns True on success."""
        payload = self._build_payload(event_data)
        try:
            resp = self.session.post(
                self._event_endpoint,
                data=json.dumps(payload),
                verify=self.verify_ssl,
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Splunk HEC returned %d: %s", resp.status_code, resp.text
                )
                return False
            return True
        except requests.RequestException as e:
            logger.error("Failed to send event to Splunk: %s", e)
            return False

    def send_batch(self, events: list[dict[str, Any]]) -> bool:
        """Send multiple events in a single request (newline-delimited JSON)."""
        if not events:
            return True

        lines = []
        for event_data in events:
            lines.append(json.dumps(self._build_payload(event_data)))
        body = "\n".join(lines)

        try:
            resp = self.session.post(
                self._event_endpoint,
                data=body,
                verify=self.verify_ssl,
                timeout=30,
            )
            if resp.status_code != 200:
                logger.warning(
                    "Splunk HEC batch returned %d: %s", resp.status_code, resp.text
                )
                return False
            return True
        except requests.RequestException as e:
            logger.error("Failed to send batch to Splunk: %s", e)
            return False

    def log_query(
        self,
        query_text: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: float = 0.0,
        source_documents_count: int = 0,
        status: str = "success",
        error_message: str = "",
    ) -> bool:
        """Convenience method for logging a RAG query event."""
        event = {
            "timestamp": time.time(),
            "event_type": "query",
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "latency_ms": round(latency_ms, 2),
            "query_text": query_text[:200],  # truncate for storage
            "source_documents_count": source_documents_count,
            "status": status,
            "error_message": error_message,
        }
        return self.send_event(event)

    def log_retrieval(
        self,
        query_text: str,
        doc_count: int,
        latency_ms: float,
    ) -> bool:
        event = {
            "timestamp": time.time(),
            "event_type": "retrieval",
            "query_text": query_text[:200],
            "source_documents_count": doc_count,
            "latency_ms": round(latency_ms, 2),
            "status": "success",
        }
        return self.send_event(event)

    def log_error(
        self,
        query_text: str,
        error_message: str,
        event_type: str = "error",
    ) -> bool:
        event = {
            "timestamp": time.time(),
            "event_type": event_type,
            "query_text": query_text[:200],
            "error_message": str(error_message),
            "status": "error",
        }
        return self.send_event(event)
