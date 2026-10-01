"""Streaming resource cleanup checks without a server or upstream connection."""

import sys
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import risk_router_core as router
from risk_router_http import Handler


class StreamingCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.enterContext(patch.object(router, "IN_FLIGHT", defaultdict(int)))
        self.update = self.enterContext(patch.object(router, "update_state"))
        self.handler = object.__new__(Handler)
        self.handler.route_order = Mock(return_value=("codex-light", "codex-qwen-local", [], ["codex-qwen-local"]))
        self.handler.send_response = Mock()
        self.handler.send_header = Mock()
        self.handler.end_headers = Mock()
        self.handler.record_request = Mock()
        self.handler.write_proxy_response = Mock()
        self.handler.wfile = Mock()
        self.response = Mock(status=200)
        self.response.headers = {"Content-Type": "text/event-stream"}
        self.response.read.side_effect = [b"data: example\n\n", b""]
        self.handler.open_stream = Mock(return_value=self.response)
        self.payload = {"model": "codex-light", "messages": [], "stream": True}

    def assert_released(self) -> None:
        self.assertEqual(router.get_in_flight("codex-qwen-local"), 0)

    def test_header_write_failure_closes_upstream_and_releases_slot(self) -> None:
        self.handler.end_headers.side_effect = BrokenPipeError("client disconnected")
        with self.assertRaises(BrokenPipeError):
            self.handler.handle_streaming_chat(self.payload)
        self.response.close.assert_called_once_with()
        self.assert_released()

    def test_failed_open_and_failed_metrics_write_release_slot(self) -> None:
        self.handler.open_stream.side_effect = OSError("upstream unavailable")
        self.update.side_effect = OSError("state is read-only")
        with self.assertRaisesRegex(OSError, "state is read-only"):
            self.handler.handle_streaming_chat(self.payload)
        self.assert_released()

    def test_upstream_close_failure_still_releases_slot(self) -> None:
        self.response.close.side_effect = OSError("close failed")
        with self.assertRaisesRegex(OSError, "close failed"):
            self.handler.handle_streaming_chat(self.payload)
        self.assert_released()

    def test_read_failure_closes_upstream_and_releases_slot(self) -> None:
        self.response.read.side_effect = OSError("read failed")
        with self.assertRaisesRegex(OSError, "read failed"):
            self.handler.handle_streaming_chat(self.payload)
        self.response.close.assert_called_once_with()
        self.assert_released()

    def test_success_forwards_stream_and_cleans_up(self) -> None:
        self.handler.handle_streaming_chat(self.payload)
        self.handler.wfile.write.assert_called_once_with(b"data: example\n\n")
        self.handler.record_request.assert_called_once()
        self.response.close.assert_called_once_with()
        self.assert_released()

    def test_retry_releases_both_candidates(self) -> None:
        self.handler.route_order.return_value = (
            "codex-light", "codex-qwen-local", [], ["codex-qwen-local", "gemini-flash-direct"]
        )

        def open_stream(path: str, payload: dict) -> Mock:
            if payload["model"] == "codex-qwen-local":
                raise OSError("first upstream unavailable")
            self.assert_released()
            return self.response

        self.handler.open_stream.side_effect = open_stream
        self.handler.handle_streaming_chat(self.payload)
        self.assertEqual(self.handler.open_stream.call_count, 2)
        self.assertEqual(router.get_in_flight("gemini-flash-direct"), 0)
        self.assert_released()


if __name__ == "__main__":
    unittest.main()
