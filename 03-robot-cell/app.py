"""Flask endpoints for the browser-local interactive robotics demonstration."""
from __future__ import annotations

from threading import Lock

from flask import Flask, jsonify, render_template, request

from robotics.simulation import RobotCell

app = Flask(__name__)
cell = RobotCell()
lock = Lock()


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def state():
    with lock:
        return jsonify(cell.state())


@app.post("/api/step")
def step():
    payload = request.get_json(silent=True) or {}
    with lock:
        try:
            result = cell.step(payload.get("dt", 0.08))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    return jsonify(result)


@app.post("/api/control")
def control():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required"}), 400
    action = payload.get("action")
    with lock:
        try:
            if action == "run":
                cell.run()
            elif action == "pause":
                cell.pause()
            elif action == "reset":
                cell.reset()
            elif action == "configure":
                cell.configure(speed=payload.get("speed"), color=payload.get("color"))
            else:
                return jsonify({"error": "Unsupported action"}), 400
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        result = cell.state()
    return jsonify(result)


@app.post("/api/wiring")
def wiring():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required"}), 400
    with lock:
        try:
            cell.edit_wiring(payload.get("action"), output=payload.get("output"), input_=payload.get("input"), preset=payload.get("preset"))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(cell.state())


if __name__ == "__main__":
    # Educational single-user local development server, not a public deployment.
    app.run(host="127.0.0.1", port=5000, debug=False)
