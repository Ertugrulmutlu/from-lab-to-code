"""Deterministic discrete-event network + robot + two control policies.

The simulated transport adds a *round trip* delay to telemetry requests and
one-way delay to a brake command. Both policies use precisely the same brake
threshold. The difference is the blocking two-sample speed measurement vs.
independent periodic telemetry polling. This is a teaching model, not a
hard-real-time system nor an actual Internet latency benchmark.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import heapq
import math
import random
from typing import Any

from .physics import Plant

DT = 0.01


@dataclass(frozen=True)
class Settings:
    target_speed: float = 10.0
    network_rtt_ms: int = 90
    jitter_ms: int = 20
    acceleration: float = 3.0
    braking: float = 4.0
    safety_margin: float = 1.2
    poll_ms: int = 50
    measurement_ms: int = 500
    seed: int = 2026

    def validated(self) -> "Settings":
        bounds = {
            "target_speed": (2, 15), "network_rtt_ms": (0, 400),
            "jitter_ms": (0, 200), "acceleration": (1, 6),
            "braking": (1, 8), "safety_margin": (0, 5),
            "poll_ms": (10, 200), "measurement_ms": (100, 900),
            "seed": (0, 9999999),
        }
        for field, (lo, hi) in bounds.items():
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
                raise ValueError(f"{field} must be in [{lo}, {hi}]")
        return self


class Simulator:
    """Single-threaded virtual-time simulator. No actual sockets involved."""

    def __init__(self, settings: Settings | None = None, mode: str = "async") -> None:
        self.settings = (settings or Settings()).validated()
        if mode not in ("async", "blocking"):
            raise ValueError("mode must be async or blocking")
        self.mode = mode
        self.plant = Plant(acceleration=self.settings.acceleration,
                           deceleration=self.settings.braking)
        self.rng = random.Random(self.settings.seed)
        self.tick = 0
        self.pending: list[tuple[int, int, str, Any]] = []
        self._serial = 0
        self.next_poll = 0
        self.phase = "idle"  # blocking phases: idle, first_pending, waiting, second_pending
        self.first: dict | None = None
        self.previous: dict | None = None
        self.estimated_speed = 0.0
        self.threshold = self.settings.safety_margin
        self.last_sensor_gap: float | None = None
        self.sensor_age_ms: float | None = None
        self.latest_sample_time: float | None = None
        self.brake_requested_at: float | None = None
        self.brake_applied_at: float | None = None
        self.finished = False
        self.result = "running"
        self.minimum_gap = self.plant.gap
        self.max_speed = 0.0
        self.deadline_misses = 0
        self.samples_received = 0
        self.requests_sent = 0
        self.network_rtts: list[float] = []
        self.events: list[dict] = []
        self.history: list[dict] = []
        self._log("system", f"Controller initialized ({mode})")
        self.plant.command_speed(self.settings.target_speed)
        self._log("motor", f"Accelerating toward {self.settings.target_speed:g} m/s")
        self._record()

    @property
    def now(self) -> float:
        return round(self.tick * DT, 6)

    def _log(self, tag: str, message: str) -> None:
        self.events.append({"t": round(self.now, 2), "tag": tag, "message": message})
        if len(self.events) > 100:
            self.events.pop(0)

    def _enqueue(self, due: int, kind: str, payload: Any = None) -> None:
        self._serial += 1
        heapq.heappush(self.pending, (due, self._serial, kind, payload))

    def _wire_delay(self) -> int:
        # The configured RTT is the baseline; jitter is additional delay.
        ms = self.settings.network_rtt_ms / 2 + self.rng.uniform(0, self.settings.jitter_ms / 2)
        return max(0, math.ceil(ms / (DT * 1000)))

    def _request(self, request: str) -> None:
        self.requests_sent += 1
        self._enqueue(self.tick + self._wire_delay(), "arrive_sensor", {"request": request, "sent_tick": self.tick})

    def _on_telemetry(self, payload: dict) -> None:
        reading = payload["reading"]
        if self.latest_sample_time is not None and reading["sampled_at"] <= self.latest_sample_time:
            return  # Avoid out-of-order telemetry corrupting the speed estimate.
        self.samples_received += 1
        self.network_rtts.append((self.tick - payload["sent_tick"]) * DT * 1000)
        self.last_sensor_gap = reading["gap"]
        self.latest_sample_time = reading["sampled_at"]
        self.sensor_age_ms = round((self.now - self.latest_sample_time) * 1000, 2)
        if self.mode == "async":
            if self.previous is not None:
                interval = reading["sampled_at"] - self.previous["sampled_at"]
                if interval > 1e-8:
                    self.estimated_speed = max(0.0, (reading["odometer"] - self.previous["odometer"]) / interval)
            self.previous = reading
            self._decide()
        elif payload["request"] == "first":
            self.first = reading
            self.phase = "waiting"
            wait_ticks = math.ceil(self.settings.measurement_ms / (DT * 1000))
            self._enqueue(self.tick + wait_ticks, "second_request")
        elif payload["request"] == "second":
            if self.first is not None:
                interval = reading["sampled_at"] - self.first["sampled_at"]
                if interval > 1e-8:
                    self.estimated_speed = max(0.0, (reading["odometer"] - self.first["odometer"]) / interval)
            self._decide()
            self.phase = "idle"
            self.next_poll = self.tick + max(1, math.ceil(self.settings.poll_ms / (DT * 1000)))

    def _decide(self) -> None:
        v = self.estimated_speed
        # One shared policy, with a fixed budget for network and scheduling.
        # The blocking controller does NOT magically account for the extra
        # 500ms it spends obtaining a speed estimate: that is the experiment.
        latency_budget = (self.settings.network_rtt_ms + self.settings.jitter_ms + self.settings.poll_ms) / 1000
        self.threshold = v * v / (2 * self.settings.braking) + v * latency_budget + self.settings.safety_margin
        if self.brake_requested_at is None and self.last_sensor_gap is not None and self.last_sensor_gap <= self.threshold:
            self.brake_requested_at = self.now
            self._log("controller", f"BRAKE requested at gap {self.last_sensor_gap:.2f} m (estimate {v:.2f} m/s)")
            self._enqueue(self.tick + self._wire_delay(), "apply_brake")

    def _handle(self, kind: str, payload: Any) -> None:
        if kind == "arrive_sensor":
            reading = self.plant.telemetry(self.now)
            self._enqueue(self.tick + self._wire_delay(), "receive_sensor", {**payload, "reading": reading})
        elif kind == "receive_sensor":
            self._on_telemetry(payload)
        elif kind == "second_request":
            if self.phase == "waiting":
                self.phase = "second_pending"
                self._request("second")
        elif kind == "apply_brake":
            if self.brake_applied_at is None:
                self.brake_applied_at = self.now
                self.plant.brake()
                self._log("motor", "Brake command reached the robot")

    def _record(self) -> None:
        self.history.append({
            "t": round(self.now, 2), "x": round(self.plant.x, 3),
            "gap": round(self.plant.gap, 3), "speed": round(self.plant.speed, 3),
            "estimate": round(self.estimated_speed, 3), "threshold": round(self.threshold, 3),
        })

    def step(self, n: int = 1) -> dict:
        for _ in range(n):
            if self.finished:
                break
            # All events due in this tick, including zero-latency messages.
            # A safety guard prevents accidental infinite event recursion.
            processed = 0
            while self.pending and self.pending[0][0] <= self.tick:
                _, _, kind, payload = heapq.heappop(self.pending)
                self._handle(kind, payload)
                processed += 1
                if processed > 1000:
                    raise RuntimeError("Network event loop did not converge")
            if self.brake_requested_at is None and self.plant.gap > 0:
                if self.mode == "async" and self.tick >= self.next_poll:
                    self._request("telemetry")
                    self.next_poll = self.tick + max(1, math.ceil(self.settings.poll_ms / (DT * 1000)))
                elif self.mode == "blocking" and self.phase == "idle" and self.tick >= self.next_poll:
                    self.phase = "first_pending"
                    self._request("first")
            self.plant.step(DT)
            self.tick += 1
            self.minimum_gap = min(self.minimum_gap, self.plant.gap)
            self.max_speed = max(self.max_speed, self.plant.speed)
            # Tick deadlines: whether controller had any pending blocking cycle.
            if self.mode == "blocking" and self.phase in ("waiting", "first_pending", "second_pending"):
                self.deadline_misses += 1
            if self.tick % 5 == 0:
                self._record()
            if self.plant.collided:
                self.finished, self.result = True, "collision"
                self._log("alert", f"Wall collision at impact speed {self.plant.speed:.2f} m/s")
            elif self.brake_applied_at is not None and self.plant.speed <= 0.001:
                self.finished, self.result = True, "safe_stop"
                self._log("success", f"Stopped with {self.plant.gap:.2f} m clearance")
            elif self.now >= 25.0:
                self.finished, self.result = True, "timeout"
                self._log("alert", "Time limit reached without stopping")
            if self.finished:
                self._record()
        return self.snapshot()

    def snapshot(self, include_history: bool = True) -> dict:
        return {
            "mode": self.mode, "settings": asdict(self.settings), "t": self.now,
            "finished": self.finished, "result": self.result,
            "robot": {"x": round(self.plant.x, 4), "radius": self.plant.radius,
                      "wall_x": self.plant.wall_x, "speed": round(self.plant.speed, 4),
                      "target": self.plant.desired_speed, "gap": round(self.plant.gap, 4),
                      "odometer": round(self.plant.odometer, 4), "collided": self.plant.collided},
            "controller": {"estimate": round(self.estimated_speed, 4),
                           "threshold": round(self.threshold, 4),
                           "sensor_gap": self.last_sensor_gap,
                           "sensor_age_ms": self.sensor_age_ms,
                           "brake_requested_at": self.brake_requested_at,
                           "brake_applied_at": self.brake_applied_at},
            "metrics": {"minimum_clearance_m": round(self.minimum_gap, 3),
                        "final_clearance_m": round(self.plant.gap, 3) if self.finished else None,
                        "max_speed_mps": round(self.max_speed, 3),
                        "sensor_requests": self.requests_sent,
                        "samples_received": self.samples_received,
                        "mean_rtt_ms": round(sum(self.network_rtts)/len(self.network_rtts), 2) if self.network_rtts else None,
                        "control_ticks_blocked": self.deadline_misses,
                        "control_time_blocked_ms": self.deadline_misses * DT * 1000,
                        "time_s": self.now},
            "events": self.events[-16:],
            **({"history": self.history} if include_history else {}),
        }

    def run(self) -> dict:
        while not self.finished:
            self.step(100)
        return self.snapshot()


def compare(settings: Settings) -> dict:
    first = Simulator(settings, "blocking").run()
    second = Simulator(settings, "async").run()
    return {"settings": asdict(settings), "blocking": first, "async": second}
