"""Example HTTP destination for Chaos Generator. Run with `just receiver`."""

import logging
from typing import Any

from fastapi import FastAPI

logger = logging.getLogger("uvicorn.error")


def create_app() -> FastAPI:
    app = FastAPI(title="Chaos Generator example receiver")
    counters = {"requests": 0, "events": 0, "last_batch_size": 0}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/events")
    async def events(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, int]:
        count = len(payload) if isinstance(payload, list) else 1
        # No await between updates: requests share one event loop per worker.
        counters["requests"] += 1
        counters["events"] += count
        counters["last_batch_size"] = count
        logger.info("Received %s events; total=%s", count, counters["events"])
        return {"accepted": count}

    @app.get("/stats")
    async def stats() -> dict[str, int]:
        return counters.copy()

    return app


app = create_app()
