"""Minimal one-dimensional robot plant, shared by replay and the TCP demo.

This is deliberately *not* a physics-accurate simulator: constant longitudinal
acceleration, finite braking, no steering, drag, tire model or sensor noise.
"""
from dataclasses import dataclass


@dataclass
class Plant:
    x: float = 8.0
    wall_x: float = 52.0
    radius: float = 1.0
    acceleration: float = 3.0
    deceleration: float = 4.0
    speed: float = 0.0
    desired_speed: float = 0.0
    odometer: float = 0.0
    collided: bool = False

    @property
    def gap(self) -> float:
        return max(0.0, self.wall_x - self.radius - self.x)

    def command_speed(self, value: float) -> None:
        self.desired_speed = max(0.0, min(float(value), 20.0))

    def brake(self) -> None:
        self.command_speed(0.0)

    def step(self, dt: float) -> None:
        if dt <= 0 or self.collided:
            return
        old = self.speed
        if self.speed < self.desired_speed:
            self.speed = min(self.desired_speed, self.speed + self.acceleration * dt)
        elif self.speed > self.desired_speed:
            self.speed = max(self.desired_speed, self.speed - self.deceleration * dt)
        # Constant acceleration over each step, integrating distance exactly
        displacement = 0.5 * (old + self.speed) * dt
        self.odometer += displacement
        self.x += displacement
        if self.x + self.radius >= self.wall_x - 1e-9:
            self.x = self.wall_x - self.radius
            self.collided = True
            # Report impact speed rather than artificially erasing it.

    def telemetry(self, sampled_at: float) -> dict:
        return {
            "sampled_at": round(sampled_at, 6),
            "gap": round(self.gap, 6),
            "odometer": round(self.odometer, 6),
            "x": round(self.x, 6),
        }
