"""Local-only FastAPI UI for the deterministic robot-control laboratory."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import threading
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from robot_lab.simulation import Settings, Simulator, compare

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="From Lab to Code #05 — Robot Control", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
_lock = threading.RLock()
_current = Simulator()


class Configuration(BaseModel):
    mode: str = "async"
    settings: dict[str, Any] = Field(default_factory=dict)


class Advance(BaseModel):
    steps: int = Field(default=8, ge=1, le=300)


def parse_config(config: Configuration) -> Settings:
    try:
        if config.mode not in ("async", "blocking"):
            raise ValueError("mode must be 'async' or 'blocking'")
        return Settings(**config.settings).validated()
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/state")
def state():
    with _lock:
        return _current.snapshot()


@app.post("/api/start")
def start(config: Configuration):
    global _current
    settings = parse_config(config)
    with _lock:
        _current = Simulator(settings, config.mode)
        return _current.snapshot()


@app.post("/api/advance")
def advance(arg: Advance):
    with _lock:
        return _current.step(arg.steps)


@app.post("/api/compare")
def run_comparison(config: Configuration):
    settings = parse_config(config)
    return compare(settings)


@app.get("/api/health")
def health():
    return {"status": "ok", "simulation_dt_ms": 10, "transport": "deterministic simulated network"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
