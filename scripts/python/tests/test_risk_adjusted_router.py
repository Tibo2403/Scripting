"""Offline regression checks for risk routing, cooldowns, and state storage."""

import json
import sys
import tempfile
import unittest
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import risk_router_core as router


class RiskAdjustedRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state_path = Path(temporary.name) / "state.json"
        self.enterContext(patch.object(router, "STATE_PATH", self.state_path))
        self.enterContext(patch.object(router, "IN_FLIGHT", defaultdict(int)))
        self.enterContext(patch.object(router, "now", return_value=1000.0))
        self.state = {"models": {}, "requests": []}

    def record(self, status: int) -> None:
        router.update_metrics(
            self.state, "gemini-flash-direct", ok=status == 200, status=status,
            total_latency_ms=2000.0, ttft_ms=500.0, tokens_per_second=50.0,
            prompt_token_estimate=100, response_tokens=20, queue_depth=0,
            error=None if status == 200 else "upstream rejected request",
        )

    def test_explicit_model_bypasses_alias_selection(self) -> None:
        with patch.object(router.random, "random") as draw:
            self.assertEqual(router.choose_model(self.state, "custom-model"), ("custom-model", []))
        draw.assert_not_called()

    def test_cooldown_excludes_model_while_an_alternative_is_available(self) -> None:
        self.record(429)
        with patch.object(router.random, "random", return_value=0.0):
            selected, choices = router.choose_model(self.state, "codex-light")
        self.assertEqual(selected, "codex-qwen-local")
        blocked = next(choice for choice in choices if choice.model == "gemini-flash-direct")
        self.assertTrue(blocked.hard_limited)
        self.assertEqual(blocked.probability, 0.0)
        self.assertIn("http_429", blocked.hard_limit_reason)

    def test_cooldown_expires_at_its_deadline(self) -> None:
        self.record(429)
        with patch.object(router, "now", return_value=1299.0):
            self.assertIsNotNone(router.hard_limit_for(self.state, "gemini-flash-direct"))
        with patch.object(router, "now", return_value=1300.0):
            self.assertIsNone(router.hard_limit_for(self.state, "gemini-flash-direct"))

    def test_concurrency_limit_excludes_busy_model_and_release_restores_it(self) -> None:
        self.assertEqual(router.acquire_in_flight("codex-qwen-local"), 0)
        with patch.object(router.random, "random", return_value=0.99):
            selected, _ = router.choose_model(self.state, "codex-light")
        self.assertEqual(selected, "gemini-flash-direct")
        router.release_in_flight("codex-qwen-local")
        router.release_in_flight("codex-qwen-local")
        self.assertEqual(router.get_in_flight("codex-qwen-local"), 0)
        self.assertIsNone(router.hard_limit_for(self.state, "codex-qwen-local"))

    def test_probabilities_sum_to_one_and_random_draw_reaches_each_candidate(self) -> None:
        selections = set()
        for draw in (0.0, 0.999999):
            with patch.object(router.random, "random", return_value=draw):
                selected, choices = router.choose_model(self.state, "codex-light")
            selections.add(selected)
            self.assertAlmostEqual(sum(choice.probability for choice in choices), 1.0)
            self.assertTrue(all(0.0 < choice.probability < 1.0 for choice in choices))
        self.assertEqual(selections, {"gemini-flash-direct", "codex-qwen-local"})

    def test_higher_error_rate_increases_risk_for_otherwise_equal_models(self) -> None:
        healthy = router.ensure_model_state(self.state, "healthy")
        failing = router.ensure_model_state(self.state, "failing")
        self.assertEqual(healthy, failing)
        failing["ewma_error_rate"] = 1.0
        risks = router.soft_risks_for(self.state, ["healthy", "failing"])
        self.assertLess(risks["healthy"], risks["failing"])

    def test_success_clears_cooldown_and_preserves_failure_count(self) -> None:
        self.record(429)
        self.record(200)
        metrics = self.state["models"]["gemini-flash-direct"]
        self.assertEqual((metrics["calls"], metrics["successes"], metrics["failures"]), (2, 1, 1))
        self.assertIsNone(metrics["last_error"])
        self.assertIsNone(metrics["hard_limit_reason"])
        self.assertEqual(metrics["hard_limited_until"], 0.0)
        summary = router.summarize_state(self.state)["models"]["gemini-flash-direct"]
        self.assertEqual(summary["success_rate"], 0.5)
        self.assertFalse(summary["hard_limited"])

    def test_failure_does_not_replace_successful_throughput_measurements(self) -> None:
        self.record(200)
        metrics = self.state["models"]["gemini-flash-direct"]
        throughput = metrics["ewma_tokens_per_second"]
        response_tokens = metrics["ewma_response_tokens"]
        self.record(503)
        self.assertEqual(metrics["ewma_tokens_per_second"], throughput)
        self.assertEqual(metrics["ewma_response_tokens"], response_tokens)
        self.assertGreater(metrics["ewma_error_rate"], 0.0)

    def test_history_retains_only_the_latest_200_requests(self) -> None:
        for number in range(205):
            router.append_request(self.state, {"number": number})
        self.assertEqual([event["number"] for event in self.state["requests"]], list(range(5, 205)))

    def test_state_round_trip_uses_the_configured_path(self) -> None:
        self.assertEqual(router.load_state(), self.state)
        self.record(200)
        router.save_state(self.state)
        self.assertEqual(router.load_state(), self.state)
        self.assertFalse(self.state_path.with_suffix(".tmp").exists())

    def test_concurrent_updates_do_not_lose_request_events(self) -> None:
        def append(number: int) -> None:
            router.update_state(lambda state: router.append_request(state, {"number": number}))

        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(append, range(40)))
        events = router.load_state()["requests"]
        self.assertEqual(sorted(event["number"] for event in events), list(range(40)))

    def test_completion_usage_takes_precedence_over_text_estimation(self) -> None:
        body = {"usage": {"completion_tokens": 12}, "choices": [{"message": {"content": "abc"}}]}
        self.assertEqual(router.extract_completion_tokens(json.dumps(body).encode()), 12)
        body["usage"]["completion_tokens"] = 0
        self.assertEqual(router.extract_completion_tokens(json.dumps(body).encode()), 0)

    def test_completion_estimation_handles_missing_usage_and_invalid_json(self) -> None:
        body = {"choices": [{"message": {"content": "abcdefgh"}}]}
        self.assertEqual(router.extract_completion_tokens(json.dumps(body).encode()), 2)
        self.assertEqual(router.extract_completion_tokens(b"not json"), 0)

    def test_response_headers_remove_forwarding_sensitive_fields_case_insensitively(self) -> None:
        headers = [("Content-Length", "100"), ("TRANSFER-ENCODING", "chunked"),
                   ("Connection", "close"), ("Content-Encoding", "gzip"),
                   ("Content-Type", "application/json"), ("X-Request-ID", "example")]
        self.assertEqual(router.response_headers(headers), headers[-2:])


if __name__ == "__main__":
    unittest.main()
