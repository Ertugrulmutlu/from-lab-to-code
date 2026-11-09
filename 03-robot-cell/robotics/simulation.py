"""Time-stepped robot-cell state machine with configurable digital I/O wiring."""
from __future__ import annotations

import math
import random
from collections import deque

from .io import IOBoard
from .kinematics import forward_kinematics, inverse_kinematics, joint_positions
from .sensors import COLORS, PICKUP_X, identify_color, item_present

SPAWN_X = -2.25
BELT_Y = 1.05
BOX_CENTER_Z = 0.78
BOX_TOP_Z = 0.92
HOME = (0.0, 0.25, 1.65)
PICKUP = (PICKUP_X, BELT_Y, BOX_TOP_Z)
PICKUP_HOVER = (PICKUP_X, BELT_Y, 1.44)
BINS = {
    "red": (-1.34, -1.75, 0.83),
    "green": (0.00, -1.86, 0.83),
    "blue": (1.34, -1.75, 0.83),
}
MOTION_PHASES = {"APPROACH", "PICKING", "LIFTING", "TRANSFER", "PLACING", "RETRACTING", "RETURNING"}


class RobotCell:
    """Local single-user teaching model. Python is authoritative for I/O and motion."""

    def __init__(self, seed: int = 13):
        self.rng = random.Random(seed)
        self.io = IOBoard()
        self.reset()

    def reset(self):
        """Reset the run without discarding user-selected I/O connections."""
        self.running = False
        self.speed = 1.0
        self.next_color = "random"
        self.phase = "IDLE"
        self.phase_elapsed = 0.0
        self.phase_duration = 0.0
        self.box = None
        self.pick_count = 0
        self.missorted = 0
        self.counts = {color: 0 for color in COLORS}
        self.bin_contents = {color: {actual: 0 for actual in COLORS} for color in COLORS}
        self.detected_color = None
        self.robot_angles = inverse_kinematics(HOME)
        self.target_angles = self.robot_angles
        self.start_angles = self.robot_angles
        self.gripping = False
        self.elapsed = 0.0
        self.fault = None
        self.events = deque(maxlen=8)
        self._log("Cell reset — ready to run")

    def edit_wiring(self, action: str, *, output: str | None = None, input_: str | None = None, preset: str | None = None):
        """Edits are allowed only while paused. Every edit restarts the run."""
        if self.running:
            raise ValueError("Pause the cell before changing I/O connections")
        if action == "connect":
            self.io.connect(output, input_)
            message = f"Connected {output} → {input_}"
        elif action == "disconnect":
            self.io.disconnect(input_)
            message = f"Disconnected input {input_}"
        elif action == "restore":
            self.io.restore()
            message = "Default I/O wiring restored"
        elif action == "preset":
            presets = ("missing_belt", "missing_gripper", "swapped_colors", "missing_position")
            if preset not in presets:
                raise ValueError("Unknown I/O experiment preset")
            self.io.restore()
            if preset == "missing_belt":
                self.io.disconnect("Belt.OnOff")
            elif preset == "missing_gripper":
                self.io.disconnect("Gripper.Vacuum")
            elif preset == "swapped_colors":
                self.io.connect("ColorSensor.Blue", "Robot.ColorRed")
                self.io.connect("ColorSensor.Red", "Robot.ColorBlue")
            elif preset == "missing_position":
                self.io.disconnect("Robot.ItemAvailable")
            message = "Loaded I/O experiment: " + preset.replace("_", " ")
        else:
            raise ValueError("Unsupported wiring action")
        self.reset()
        self._log(message)

    def _log(self, message: str):
        self.events.appendleft({"time": round(self.elapsed, 1), "message": message})

    def run(self):
        if self.phase == "FAULT":
            raise ValueError("Reset the simulation to clear the fault")
        if not self.running:
            self.running = True
            self._log("Simulation started")

    def pause(self):
        if self.running:
            self.running = False
            self._log("Simulation paused")

    def configure(self, *, speed: float | None = None, color: str | None = None):
        if speed is not None:
            if not isinstance(speed, (float, int)) or isinstance(speed, bool) or not math.isfinite(speed) or not 0.25 <= speed <= 3.0:
                raise ValueError("Speed must be between 0.25 and 3.0")
            self.speed = float(speed)
        if color is not None:
            if color not in (*COLORS, "random"):
                raise ValueError("Color must be random, red, green, or blue")
            self.next_color = color

    def _outputs(self) -> dict[str, bool]:
        at_pickup = item_present(self.box)
        raw_color = identify_color(self.box) if at_pickup else None
        return {
            "Robot.Generate": self.running and self.phase == "IDLE",
            "Robot.StartStop": self.running and self.phase == "CONVEYING",
            "Robot.Grasp": self.phase in {"LIFTING", "TRANSFER", "PLACING"},
            "Robot.RemoveRed": self.phase == "PLACING" and self.detected_color == "red",
            "Robot.RemoveGreen": self.phase == "PLACING" and self.detected_color == "green",
            "Robot.RemoveBlue": self.phase == "PLACING" and self.detected_color == "blue",
            "PositionSensor.Detect": bool(at_pickup),
            "ColorSensor.Red": raw_color == "red",
            "ColorSensor.Green": raw_color == "green",
            "ColorSensor.Blue": raw_color == "blue",
        }

    def _inputs(self) -> dict[str, bool]:
        return self.io.resolve(self._outputs())

    def _spawn(self):
        chosen = self.rng.choice(COLORS) if self.next_color == "random" else self.next_color
        self.box = {"x": SPAWN_X, "y": BELT_Y, "z": BOX_CENTER_Z, "color": chosen, "attached": False}
        self.detected_color = None
        self.phase = "CONVEYING"
        self._log(f"Generated a {chosen} box")

    def _motion(self, phase: str, target: tuple[float, float, float], duration: float):
        self.phase = phase
        self.phase_elapsed = 0.0
        self.phase_duration = duration
        self.start_angles = self.robot_angles
        self.target_angles = inverse_kinematics(target)
        self._log(phase.replace("_", " ").capitalize())

    def _fault(self, message: str):
        self.fault = message
        self.running = False
        self.gripping = False
        if self.box:
            self.box["attached"] = False
        self.phase = "FAULT"
        self._log("I/O fault: " + message)

    def _after_motion(self):
        if self.phase == "APPROACH":
            self._motion("PICKING", PICKUP, 0.75)
        elif self.phase == "PICKING":
            # Robot.Grasp command goes high in LIFTING; it must reach Gripper.Vacuum.
            self._motion("LIFTING", PICKUP_HOVER, 0.75)
            if not self._inputs()["Gripper.Vacuum"]:
                self._fault("Vacuum gripper has no active Grasp signal")
                return
            self.gripping = True
            if self.box:
                self.box["attached"] = True
            self._log("Vacuum gripper engaged")
        elif self.phase == "LIFTING":
            color = self.detected_color
            if color is None:
                self._fault("Cannot transfer an unknown item")
                return
            bx, by, _ = BINS[color]
            self._motion("TRANSFER", (bx, by, 1.48), 1.35)
        elif self.phase == "TRANSFER":
            self._motion("PLACING", BINS[self.detected_color], 0.72)
        elif self.phase == "PLACING":
            destination = self.detected_color
            sink_port = {"red": "RedSink.Remove", "green": "GreenSink.Remove", "blue": "BlueSink.Remove"}[destination]
            if not self._inputs()[sink_port]:
                self._fault(f"{destination.capitalize()} sink has no Remove signal")
                return
            actual = self.box["color"] if self.box else None
            self.gripping = False
            self.box = None  # the selected sink removes the part from the scene
            if actual == destination:
                self.counts[actual] += 1
                self.pick_count += 1
                self._log(f"Correctly sorted {actual}")
            else:
                self.missorted += 1
                self._log(f"MIS-SORTED: {actual} item went to {destination} sink")
            if actual in COLORS:
                self.bin_contents[destination][actual] += 1
            bx, by, _ = BINS[destination]
            self._motion("RETRACTING", (bx, by, 1.48), 0.65)
        elif self.phase == "RETRACTING":
            self._motion("RETURNING", HOME, 1.15)
        elif self.phase == "RETURNING":
            self.phase = "IDLE"

    def _diagnostic(self, inputs: dict[str, bool]) -> str:
        if self.fault:
            return self.fault
        if not self.running:
            return "Paused — select an output and an input to edit the wiring."
        if self.phase == "IDLE" and not inputs["Source.Trigger"]:
            return "Waiting: Source.Trigger is not receiving Robot.Generate."
        if self.phase == "CONVEYING" and not inputs["Belt.OnOff"]:
            return "Waiting: Belt.OnOff is LOW; conveyor cannot move."
        if self.phase == "CONVEYING" and self.box and item_present(self.box) and not inputs["Robot.ItemAvailable"]:
            return "Waiting: position sensor is not reaching Robot.ItemAvailable."
        if self.phase == "CONVEYING" and self.box and item_present(self.box):
            colors = [c for c in COLORS if inputs[f"Robot.Color{c.capitalize()}"]]
            if len(colors) != 1:
                return "Waiting: connect exactly one active color sensor signal."
        return "All required signals for the current phase are available."

    def step(self, dt: float = 0.08):
        """Advance one tick using wired I/O levels, independently of render FPS."""
        if not isinstance(dt, (float, int)) or isinstance(dt, bool) or not math.isfinite(dt):
            raise ValueError("dt must be a finite number")
        if not self.running:
            return self.state()
        dt = max(0.0, min(float(dt), 0.2)) * self.speed
        self.elapsed += dt

        if self.phase == "IDLE" and self._inputs()["Source.Trigger"]:
            self._spawn()

        if self.phase == "CONVEYING":
            if self._inputs()["Belt.OnOff"] and self.box is not None:
                self.box["x"] = min(PICKUP_X, self.box["x"] + 1.20 * dt)
            inputs = self._inputs()
            if inputs["Robot.ItemAvailable"] and item_present(self.box):
                matched = [c for c in COLORS if inputs[f"Robot.Color{c.capitalize()}"]]
                if len(matched) == 1:
                    self.detected_color = matched[0]
                    self.phase = "DETECTED"
                    self.phase_elapsed = 0.0
                    self._log(f"Robot input detected: {self.detected_color}")
        elif self.phase == "DETECTED":
            self.phase_elapsed += dt
            if self.phase_elapsed >= 0.32:
                self._motion("APPROACH", PICKUP_HOVER, 1.10)
        elif self.phase in MOTION_PHASES:
            self.phase_elapsed = min(self.phase_duration, self.phase_elapsed + dt)
            t = self.phase_elapsed / self.phase_duration
            smooth = t * t * (3.0 - 2.0 * t)
            self.robot_angles = tuple(a + (b - a) * smooth for a, b in zip(self.start_angles, self.target_angles))
            if self.box is not None and self.gripping:
                x, y, z = forward_kinematics(self.robot_angles)
                self.box.update({"x": x, "y": y, "z": z - (BOX_TOP_Z - BOX_CENTER_Z)})
            if self.phase_elapsed >= self.phase_duration:
                self.robot_angles = self.target_angles
                self._after_motion()
        return self.state()

    def state(self) -> dict:
        outputs = self._outputs()
        inputs = self.io.resolve(outputs)
        return {
            "running": self.running,
            "phase": self.phase,
            "speed": self.speed,
            "next_color": self.next_color,
            "detected_color": self.detected_color,
            "box": dict(self.box) if self.box else None,
            "robot": {
                "angles_deg": [round(math.degrees(a), 2) for a in self.robot_angles],
                "joints": joint_positions(self.robot_angles),
                "gripping": self.gripping,
            },
            "counts": dict(self.counts),
            "bin_contents": {k: dict(v) for k, v in self.bin_contents.items()},
            "total": self.pick_count,
            "missorted": self.missorted,
            "elapsed": round(self.elapsed, 2),
            "events": list(self.events),
            "fault": self.fault,
            "diagnostic": self._diagnostic(inputs),
            "wiring": self.io.as_dict(outputs),
        }
