"""A bounded, sequential HTTP traffic worker independent of the Streamlit UI."""

import math
import random
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

import requests


@dataclass(frozen=True)
class RunConfig:
    url: str
    rate: int
    mode: str
    interval: float

    def validate(self) -> None:
        try:
            parsed = urlsplit(self.url)
            valid = parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port != 0
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Enter a valid HTTP or HTTPS destination URL.")
        if not 1 <= self.rate <= 1000:
            raise ValueError("Events/second must be between 1 and 1000.")
        if self.mode not in {"Real-time", "Batch", "Micro-batch"}:
            raise ValueError("Select a supported streaming type.")
        if not 0.1 <= self.interval <= 60:
            raise ValueError("Request interval must be between 0.1 and 60 seconds.")


class TrafficRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stats = self._empty_stats()

    @staticmethod
    def _empty_stats() -> dict:
        return {"events": 0, "requests": 0, "errors": 0, "status": None, "error": ""}

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def snapshot(self) -> dict:
        with self._lock:
            return self._stats.copy()

    def start(self, config: RunConfig) -> None:
        config.validate()
        if self.is_running:
            raise ValueError("Stop the current run before starting another.")
        with self._lock:
            self._stats = self._empty_stats()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(config,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self, config: RunConfig) -> None:
        realtime = config.mode == "Real-time"
        period = 1 / config.rate if realtime else config.interval
        deadline = time.monotonic() + (0 if realtime else period)
        pending = 0.0
        sequence = 0
        run_id = str(uuid4())
        with requests.Session() as session:
            while not self._stop.wait(max(0, deadline - time.monotonic())):
                started = time.monotonic()
                pending += 1 if realtime else config.rate * period
                count = math.floor(pending + 1e-9)
                pending -= count
                payload = []
                for _ in range(count):
                    sequence += 1
                    payload.append(
                        {
                            "id": str(uuid4()),
                            "run_id": run_id,
                            "sequence": sequence,
                            "timestamp": datetime.now(UTC).isoformat(),
                            "value": random.random(),
                        }
                    )
                if payload and not self._stop.is_set():
                    self._send(session, config.url, payload[0] if realtime else payload, count)
                # Slow requests reduce throughput; never replay missed windows in a burst.
                deadline = max(started + period, time.monotonic())

    def _send(self, session: requests.Session, url: str, payload: dict | list, count: int) -> None:
        try:
            # Do not buffer response bodies or follow redirects to another destination.
            with session.post(
                url, json=payload, timeout=(3, 5), allow_redirects=False, stream=True
            ) as response:
                success = 200 <= response.status_code < 300
                with self._lock:
                    self._stats["status"] = response.status_code
                    self._stats["events"] += count if success else 0
                    self._stats["requests"] += int(success)
                    self._stats["errors"] += int(not success)
                    self._stats["error"] = "" if success else f"HTTP {response.status_code}"
        except requests.RequestException as error:
            with self._lock:
                self._stats["status"] = None
                self._stats["errors"] += 1
                self._stats["error"] = str(error)
