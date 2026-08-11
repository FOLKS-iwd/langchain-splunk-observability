import json
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from splunk_logger import SplunkHECLogger


class TestSplunkHECLogger(unittest.TestCase):

    def setUp(self):
        with patch("splunk_logger.Config") as mock_cfg:
            mock_cfg.SPLUNK_HEC_URL = "https://splunk.local:8088"
            mock_cfg.SPLUNK_HEC_TOKEN = "test-token-123"
            mock_cfg.SPLUNK_INDEX = "llm_observability"
            mock_cfg.SPLUNK_SOURCETYPE = "langchain_events"
            self.logger = SplunkHECLogger(
                hec_url="https://splunk.local:8088",
                hec_token="test-token-123",
                index="llm_observability",
                sourcetype="langchain_events",
            )

    def test_event_endpoint_construction(self):
        self.assertEqual(
            self.logger._event_endpoint,
            "https://splunk.local:8088/services/collector/event",
        )

    def test_endpoint_strips_trailing_slash(self):
        with patch("splunk_logger.Config") as mock_cfg:
            mock_cfg.SPLUNK_HEC_URL = "https://splunk.local:8088/"
            mock_cfg.SPLUNK_HEC_TOKEN = "tok"
            mock_cfg.SPLUNK_INDEX = "idx"
            mock_cfg.SPLUNK_SOURCETYPE = "st"
            logger = SplunkHECLogger(hec_url="https://splunk.local:8088/")
        self.assertTrue(
            logger._event_endpoint.startswith("https://splunk.local:8088/services")
        )

    def test_build_payload_structure(self):
        event_data = {"event_type": "query", "query_text": "test"}
        payload = self.logger._build_payload(event_data)
        self.assertIn("time", payload)
        self.assertEqual(payload["index"], "llm_observability")
        self.assertEqual(payload["sourcetype"], "langchain_events")
        self.assertEqual(payload["source"], "langchain_rag")
        self.assertEqual(payload["event"]["event_type"], "query")

    @patch.object(SplunkHECLogger, "_build_session")
    def test_send_event_success(self, mock_build):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        self.logger.session = mock_session

        result = self.logger.send_event({"event_type": "query", "query_text": "q"})
        self.assertTrue(result)
        mock_session.post.assert_called_once()

    @patch.object(SplunkHECLogger, "_build_session")
    def test_send_event_failure_status(self, mock_build):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_session.post.return_value = mock_response
        self.logger.session = mock_session

        result = self.logger.send_event({"event_type": "query"})
        self.assertFalse(result)

    @patch.object(SplunkHECLogger, "_build_session")
    def test_send_event_request_exception(self, mock_build):
        import requests
        mock_session = MagicMock()
        mock_session.post.side_effect = requests.RequestException("Connection refused")
        self.logger.session = mock_session

        result = self.logger.send_event({"event_type": "error"})
        self.assertFalse(result)

    @patch.object(SplunkHECLogger, "_build_session")
    def test_send_batch_empty_list(self, mock_build):
        result = self.logger.send_batch([])
        self.assertTrue(result)

    @patch.object(SplunkHECLogger, "_build_session")
    def test_send_batch_multiple_events(self, mock_build):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response
        self.logger.session = mock_session

        events = [
            {"event_type": "query", "query_text": "q1"},
            {"event_type": "query", "query_text": "q2"},
            {"event_type": "query", "query_text": "q3"},
        ]
        result = self.logger.send_batch(events)
        self.assertTrue(result)

        posted_body = mock_session.post.call_args.kwargs.get(
            "data", mock_session.post.call_args[1].get("data", "")
        )
        lines = posted_body.strip().split("\n")
        self.assertEqual(len(lines), 3)

    def test_log_query_convenience(self):
        self.logger.send_event = MagicMock(return_value=True)
        result = self.logger.log_query(
            query_text="test question",
            model_name="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=320.5,
        )
        self.assertTrue(result)
        self.logger.send_event.assert_called_once()
        event = self.logger.send_event.call_args[0][0]
        self.assertEqual(event["event_type"], "query")
        self.assertEqual(event["model_name"], "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()
