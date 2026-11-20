"""Optional *real* TCP transport demonstration using the same robot plant.

Usage in different terminals:
    python -m robot_lab.tcp_demo server --port 30352
    python -m robot_lab.tcp_demo client --port 30352

JSON-lines over loopback, not the university protocol. Real wall-clock latency
and local OS scheduling are involved; results are not comparable to the virtual
simulator's reproducible latency sweep.
"""
from __future__ import annotations
import argparse
import json
import socket
import socketserver
import threading
import time
from .physics import Plant


class Arena:
    def __init__(self) -> None:
        self.plant = Plant()
        self.lock = threading.RLock()
        self.last = time.monotonic()

    def handle(self, message: dict) -> dict:
        with self.lock:
            now = time.monotonic()
            elapsed = min(2.0, max(0.0, now - self.last))
            self.last = now
            while elapsed > 0:
                dt = min(0.01, elapsed)
                self.plant.step(dt)
                elapsed -= dt
            command = message.get("type")
            if command == "reset":
                self.plant = Plant()
            elif command == "set_speed":
                try:
                    value = float(message["value"])
                except (KeyError, ValueError, TypeError):
                    return {"ok": False, "error": "set_speed requires numeric value"}
                if not 0 <= value <= 15:
                    return {"ok": False, "error": "speed must be in [0, 15]"}
                self.plant.command_speed(value)
            elif command == "brake":
                self.plant.brake()
            elif command != "telemetry":
                return {"ok": False, "error": "unknown command"}
            return {"ok": True, "type": command, "telemetry": {
                **self.plant.telemetry(now), "speed_truth": round(self.plant.speed, 4),
                "collision": self.plant.collided}}


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        self.request.settimeout(10)
        while True:
            try:
                line = self.rfile.readline(4097)
                if not line:
                    return
                if len(line) > 4096:
                    return
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError("expected object")
                result = self.server.arena.handle(message)
            except (ValueError, json.JSONDecodeError, KeyError):
                result = {"ok": False, "error": "invalid JSON request"}
            except (TimeoutError, OSError):
                return
            self.wfile.write((json.dumps(result) + "\n").encode())


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address):
        super().__init__(address, Handler)
        self.arena = Arena()


def exchange(file, message: dict) -> dict:
    file.write((json.dumps(message) + "\n").encode())
    file.flush()
    line = file.readline()
    if not line:
        raise ConnectionError("server closed connection")
    return json.loads(line)


def client(host: str, port: int, target_speed: float = 10.0) -> None:
    with socket.create_connection((host, port), timeout=3) as sock:
        with sock.makefile("rwb") as file:
            exchange(file, {"type": "reset"})
            exchange(file, {"type": "set_speed", "value": target_speed})
            prev = None
            applied = False
            print("Connected to independent TCP arena. Ctrl+C to quit.")
            for _ in range(350):
                result = exchange(file, {"type": "telemetry"})
                current = result["telemetry"]
                estimated = 0.0
                if prev:
                    dt = current["sampled_at"] - prev["sampled_at"]
                    if dt > 0:
                        estimated = (current["odometer"] - prev["odometer"]) / dt
                threshold = estimated**2 / 8.0 + estimated * 0.12 + 1.2
                print(f"gap={current['gap']:6.2f}m | speed={estimated:5.2f}m/s | threshold={threshold:5.2f}m", end="\r", flush=True)
                if prev and not applied and current["gap"] <= threshold:
                    exchange(file, {"type": "brake"})
                    applied = True
                    print("\nBrake command sent over TCP")
                if current["collision"]:
                    print("\nCollision")
                    break
                if applied and current["speed_truth"] <= 0.02:
                    print(f"\nStopped with {current['gap']:.2f}m clearance")
                    break
                prev = current
                time.sleep(0.05)


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent JSON-lines TCP arena")
    parser.add_argument("role", choices=["server", "client"])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=30352)
    parser.add_argument("--speed", type=float, default=10.0)
    args = parser.parse_args()
    if args.role == "server":
        with Server((args.host, args.port)) as server:
            print(f"Arena listening on {args.host}:{server.server_address[1]}")
            server.serve_forever()
    else:
        client(args.host, args.port, args.speed)


if __name__ == "__main__":
    main()
