import time
import unittest
from unittest.mock import MagicMock, patch

from observability import LLMObserver, QueryStats


class TestQueryStats(unittest.TestCase):

    def setUp(self):
        self.stats = QueryStats()

    def test_initial_state(self):
        self.assertEqual(self.stats.total_queries, 0)
        self.assertEqual(self.stats.total_errors, 0)
        self.assertEqual(self.stats.avg_latency_ms, 0.0)
        self.assertEqual(self.stats.error_rate, 0.0)

    def test_record_single_query(self):
        self.stats.record_query(latency_ms=150.0, tokens=200)
        self.assertEqual(self.stats.total_queries, 1)
        self.assertEqual(self.stats.total_tokens_used, 200)
        self.assertEqual(self.stats.avg_latency_ms, 150.0)

    def test_avg_latency_multiple_queries(self):
        self.stats.record_query(latency_ms=100.0, tokens=50)
        self.stats.record_query(latency_ms=300.0, tokens=150)
        self.assertEqual(self.stats.total_queries, 2)
        self.assertEqual(self.stats.avg_latency_ms, 200.0)

    def test_error_rate_calculation(self):
        self.stats.record_query(latency_ms=100.0, tokens=50)
        self.stats.record_query(latency_ms=200.0, tokens=0, is_error=True)
        self.stats.record_query(latency_ms=100.0, tokens=50)
        self.stats.record_query(latency_ms=300.0, tokens=0, is_error=True)
        self.assertEqual(self.stats.total_errors, 2)
        self.assertAlmostEqual(self.stats.error_rate, 0.5)

    def test_to_dict(self):
        self.stats.record_query(latency_ms=500.0, tokens=100)
        d = self.stats.to_dict()
        self.assertIn("total_queries", d)
        self.assertIn("avg_latency_ms", d)
        self.assertIn("error_rate", d)
        self.assertIn("total_tokens_used", d)
        self.assertEqual(d["total_queries"], 1)


class TestLLMObserver(unittest.TestCase):

    def setUp(self):
        self.mock_splunk = MagicMock()
        self.observer = LLMObserver(splunk_logger=self.mock_splunk)

    def test_track_latency_context_manager(self):
        with self.observer.track_latency() as timing:
            time.sleep(0.05)
        self.assertIn("latency_ms", timing)
        self.assertGreaterEqual(timing["latency_ms"], 40.0)

    def test_observe_query_updates_stats(self):
        result = {
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
            "source_documents_count": 3,
            "model_name": "gpt-4o-mini",
        }
        self.observer.observe_query("test query", result, latency_ms=250.0)
        self.assertEqual(self.observer.stats.total_queries, 1)
        self.assertEqual(self.observer.stats.total_tokens_used, 150)
        self.mock_splunk.log_query.assert_called_once()

    def test_observe_query_event_fields(self):
        result = {
            "token_usage": {
                "prompt_tokens": 80,
                "completion_tokens": 40,
                "total_tokens": 120,
            },
            "source_documents_count": 2,
            "model_name": "gpt-4o-mini",
        }
        self.observer.observe_query("question SOC", result, latency_ms=300.0)
        call_kwargs = self.mock_splunk.log_query.call_args
        self.assertEqual(call_kwargs.kwargs.get("prompt_tokens", call_kwargs[1].get("prompt_tokens", None)), 80)

    def test_observe_error_increments_error_count(self):
        error = RuntimeError("API timeout")
        self.observer.observe_error("failing query", error, latency_ms=5000.0)
        self.assertEqual(self.observer.stats.total_errors, 1)
        self.mock_splunk.log_error.assert_called_once()

    def test_observe_retrieval_sends_event(self):
        self.observer.observe_retrieval("search query", doc_count=4, latency_ms=80.0)
        self.mock_splunk.log_retrieval.assert_called_once_with(
            "search query", 4, 80.0
        )


if __name__ == "__main__":
    unittest.main()
