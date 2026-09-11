import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from receiver import create_app  # noqa: E402


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_receives_objects_and_batches_without_retaining_payloads(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        event = {"id": "example", "sequence": 1, "value": 0.42}
        for payload, count in ((event, 1), ([event] * 3, 3), ([], 0)):
            response = self.client.post("/events", json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"accepted": count})
        self.assertEqual(
            self.client.get("/stats").json(),
            {"requests": 3, "events": 4, "last_batch_size": 0},
        )

    def test_rejects_invalid_payloads_without_counting_them(self):
        for payload in (42, "text", None, [1, 2]):
            self.assertEqual(self.client.post("/events", json=payload).status_code, 422)
        self.assertEqual(self.client.get("/stats").json()["requests"], 0)


if __name__ == "__main__":
    unittest.main()
