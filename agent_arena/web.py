"""Flask web app: the live Agent Arena dashboard.

Run with ``python app.py``, then open http://127.0.0.1:5000.
Pick a topic, hit "Start Debate", and watch every agent's thinking trace,
tool calls, arguments, fact-checks, and the final verdict stream in live.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request

from .bus import Event, MessageBus
from .debate import DebateOrchestrator
from .tools import FactBase

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class LiveBus(MessageBus):
    """A bus that also appends every event to a shared live log."""

    def __init__(self, log: List[Dict[str, Any]]) -> None:
        super().__init__()
        self._log = log

    def publish(self, kind: str, agent: str, text: str, round: str = "") -> Event:
        event = super().publish(kind, agent, text, round)
        self._log.append(event.to_dict())
        return event


def create_app() -> Flask:
    app = Flask(__name__)
    state: Dict[str, Any] = {"runs": {}, "counter": 0}
    lock = threading.Lock()

    with open(DATA_DIR / "topics.json", encoding="utf-8") as fh:
        topics = json.load(fh)["topics"]

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/topics")
    def list_topics():
        return jsonify(topics)

    @app.post("/api/start")
    def start_debate():
        payload = request.get_json(silent=True) or {}
        topic = payload.get("topic", "pineapple-pizza")
        try:
            FactBase().motion(topic)
        except KeyError:
            return jsonify({"error": f"Unknown topic '{topic}'"}), 400

        with lock:
            state["counter"] += 1
            run_id = f"run-{state['counter']}"
            log: List[Dict[str, Any]] = []
            state["runs"][run_id] = {"log": log, "result": None, "done": False}

        def _run() -> None:
            bus = LiveBus(log)
            orchestrator = DebateOrchestrator(topic=topic, bus=bus)
            result = orchestrator.run()
            with lock:
                state["runs"][run_id]["result"] = result
                state["runs"][run_id]["done"] = True

        threading.Thread(target=_run, daemon=True).start()
        return jsonify({"run_id": run_id, "topic": topic})

    @app.get("/api/events")
    def events():
        run_id = request.args.get("run_id", "")
        since = int(request.args.get("since", "0"))
        run = state["runs"].get(run_id)
        if run is None:
            return jsonify({"error": "Unknown run_id"}), 404
        with lock:
            new_events = [e for e in run["log"] if e["seq"] > since]
            done = run["done"]
        return jsonify({"events": new_events, "done": done})

    @app.get("/api/result")
    def result():
        run_id = request.args.get("run_id", "")
        run = state["runs"].get(run_id)
        if run is None:
            return jsonify({"error": "Unknown run_id"}), 404
        with lock:
            return jsonify({"done": run["done"], "result": run["result"]})

    return app
