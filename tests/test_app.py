import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from generator import RunConfig, TrafficRunner  # noqa: E402


class TrafficTests(unittest.TestCase):
    def setUp(self):
        self.runner = TrafficRunner()
        self.session = MagicMock()
        self.session.post.return_value.__enter__.return_value.status_code = 202
        self.session_patch = patch("generator.requests.Session")
        self.session_patch.start().return_value.__enter__.return_value = self.session
        self.addCleanup(self.session_patch.stop)
        self.addCleanup(self.stop)

    def stop(self):
        self.runner.stop()
        if self.runner._thread:
            self.runner._thread.join(timeout=2)
        self.assertFalse(self.runner.is_running)

    def wait_for_requests(self, count):
        deadline = time.monotonic() + 2
        while self.session.post.call_count < count and time.monotonic() < deadline:
            time.sleep(0.005)
        self.assertGreaterEqual(self.session.post.call_count, count)

    def test_real_time_payload_pacing_and_restart(self):
        self.runner.start(RunConfig("http://localhost/events", 10, "Real-time", 1))
        self.wait_for_requests(3)
        self.stop()
        calls = list(self.session.post.call_args_list)
        self.assertLessEqual(len(calls), 4)
        self.assertEqual(
            [c.kwargs["json"]["sequence"] for c in calls], list(range(1, len(calls) + 1))
        )
        self.assertEqual(self.runner.snapshot()["events"], len(calls))
        run_id = calls[0].kwargs["json"]["run_id"]
        self.runner.start(RunConfig("http://localhost/events", 1, "Real-time", 1))
        self.wait_for_requests(len(calls) + 1)
        self.stop()
        self.assertNotEqual(self.session.post.call_args.kwargs["json"]["run_id"], run_id)
        self.assertEqual(self.runner.snapshot()["events"], 1)

    def test_batch_modes_wait_and_preserve_fractional_events(self):
        for mode in ("Batch", "Micro-batch"):
            with self.subTest(mode=mode):
                self.session.reset_mock()
                self.runner.start(RunConfig("http://localhost/events", 15, mode, 0.1))
                self.assertEqual(self.session.post.call_count, 0)
                self.wait_for_requests(2)
                self.stop()
                sizes = [len(c.kwargs["json"]) for c in self.session.post.call_args_list]
                self.assertEqual(sizes[:2], [1, 2])
                self.assertEqual(self.runner.snapshot()["events"], sum(sizes))

    def test_stop_interrupts_long_wait(self):
        self.runner.start(RunConfig("http://localhost/events", 10, "Batch", 60))
        self.stop()
        self.session.post.assert_not_called()

    def test_duplicate_start_and_stop_during_request(self):
        entered, release = threading.Event(), threading.Event()

        def slow_post(*args, **kwargs):
            entered.set()
            release.wait(timeout=1)
            response = MagicMock()
            response.__enter__.return_value.status_code = 200
            return response

        self.session.post.side_effect = slow_post
        config = RunConfig("http://localhost/events", 10, "Real-time", 1)
        self.runner.start(config)
        self.assertTrue(entered.wait(timeout=1))
        with self.assertRaises(ValueError):
            self.runner.start(config)
        self.runner.stop()
        self.assertTrue(self.runner.stopping)
        release.set()
        self.stop()
        self.assertEqual(self.session.post.call_count, 1)

    def test_http_failure_and_timeout_are_counted(self):
        self.session.post.return_value.__enter__.return_value.status_code = 503
        self.runner._send(self.session, "http://localhost/events", {}, 1)
        self.assertEqual(self.runner.snapshot()["errors"], 1)
        self.assertEqual(self.runner.snapshot()["events"], 0)
        self.session.post.side_effect = requests.Timeout("timed out")
        self.runner._send(self.session, "http://localhost/events", {}, 1)
        self.assertEqual(self.runner.snapshot()["errors"], 2)
        self.assertEqual(self.runner.snapshot()["error"], "timed out")

    def test_invalid_destination(self):
        for url in ("", "ftp://example.com", "http://", "http://[bad", "http://host:bad"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.runner.start(RunConfig(url, 10, "Real-time", 1))


class InterfaceTests(unittest.TestCase):
    def test_controls_validation_and_start_stop(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "src/main.py")).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.number_input[0].disabled)
        app.button[0].click().run()
        self.assertIn("valid HTTP", app.error[0].value)
        app.selectbox[0].select("Batch").run()
        self.assertEqual(app.number_input[0].value, 10.0)
        app.text_input[0].input("http://localhost:8000/events").run()
        app.button[0].click().run()
        runner = app.session_state["runner"]
        try:
            self.assertFalse(app.exception)
            self.assertTrue(runner.is_running)
            self.assertTrue(app.button[0].disabled)
            app.button[1].click().run()
            runner._thread.join(timeout=1)
            app.run()
            self.assertFalse(app.exception)
            self.assertFalse(runner.is_running)
            self.assertFalse(app.button[0].disabled)
        finally:
            runner.stop()


if __name__ == "__main__":
    unittest.main()
