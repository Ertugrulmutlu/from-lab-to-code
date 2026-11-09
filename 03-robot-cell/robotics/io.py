"""Discrete digital I/O board for an educational robot cell.

Connections always run from a device OUTPUT to a device INPUT.  This is a
logical (not electrical) model: Boolean levels, one source per input, no
propagation delay or PLC scan-cycle emulation.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Port:
    id: str
    label: str
    group: str

    def as_dict(self) -> dict[str, str]:
        return {"id": self.id, "label": self.label, "group": self.group}


OUTPUTS = (
    Port("Robot.Generate", "Generate", "ROBOT OUTPUTS"),
    Port("Robot.StartStop", "StartStop", "ROBOT OUTPUTS"),
    Port("Robot.Grasp", "Grasp", "ROBOT OUTPUTS"),
    Port("Robot.RemoveRed", "RemoveRed", "ROBOT OUTPUTS"),
    Port("Robot.RemoveGreen", "RemoveGreen", "ROBOT OUTPUTS"),
    Port("Robot.RemoveBlue", "RemoveBlue", "ROBOT OUTPUTS"),
    Port("PositionSensor.Detect", "Detect", "SENSOR OUTPUTS"),
    Port("ColorSensor.Red", "Red", "SENSOR OUTPUTS"),
    Port("ColorSensor.Green", "Green", "SENSOR OUTPUTS"),
    Port("ColorSensor.Blue", "Blue", "SENSOR OUTPUTS"),
)

INPUTS = (
    Port("Source.Trigger", "Trigger", "DEVICE INPUTS"),
    Port("Belt.OnOff", "OnOff", "DEVICE INPUTS"),
    Port("Gripper.Vacuum", "Vacuum", "DEVICE INPUTS"),
    Port("RedSink.Remove", "Red Remove", "DEVICE INPUTS"),
    Port("GreenSink.Remove", "Green Remove", "DEVICE INPUTS"),
    Port("BlueSink.Remove", "Blue Remove", "DEVICE INPUTS"),
    Port("Robot.ItemAvailable", "ItemAvailable", "ROBOT INPUTS"),
    Port("Robot.ColorRed", "ColorRed", "ROBOT INPUTS"),
    Port("Robot.ColorGreen", "ColorGreen", "ROBOT INPUTS"),
    Port("Robot.ColorBlue", "ColorBlue", "ROBOT INPUTS"),
)

DEFAULT_CONNECTIONS = {
    "Source.Trigger": "Robot.Generate",
    "Belt.OnOff": "Robot.StartStop",
    "Gripper.Vacuum": "Robot.Grasp",
    "RedSink.Remove": "Robot.RemoveRed",
    "GreenSink.Remove": "Robot.RemoveGreen",
    "BlueSink.Remove": "Robot.RemoveBlue",
    "Robot.ItemAvailable": "PositionSensor.Detect",
    "Robot.ColorRed": "ColorSensor.Red",
    "Robot.ColorGreen": "ColorSensor.Green",
    "Robot.ColorBlue": "ColorSensor.Blue",
}
OUTPUT_IDS = frozenset(p.id for p in OUTPUTS)
INPUT_IDS = frozenset(p.id for p in INPUTS)


class IOBoard:
    """User-editable one-to-one *input* mapping; an output may fan out."""

    def __init__(self):
        self.routes: dict[str, str] = dict(DEFAULT_CONNECTIONS)

    def connect(self, output: str, input_: str) -> None:
        if not isinstance(output, str) or output not in OUTPUT_IDS:
            raise ValueError("Choose a valid output port")
        if not isinstance(input_, str) or input_ not in INPUT_IDS:
            raise ValueError("Choose a valid input port")
        self.routes[input_] = output

    def disconnect(self, input_: str) -> None:
        if not isinstance(input_, str) or input_ not in INPUT_IDS:
            raise ValueError("Choose a valid input port")
        self.routes.pop(input_, None)

    def restore(self) -> None:
        self.routes = dict(DEFAULT_CONNECTIONS)

    def resolve(self, outputs: dict[str, bool]) -> dict[str, bool]:
        return {p.id: bool(outputs.get(self.routes.get(p.id, ""), False)) for p in INPUTS}

    def as_dict(self, outputs: dict[str, bool]) -> dict:
        inputs = self.resolve(outputs)
        return {
            "outputs": [p.as_dict() for p in OUTPUTS],
            "inputs": [p.as_dict() for p in INPUTS],
            "connections": [
                {"output": self.routes[p.id], "input": p.id}
                for p in INPUTS if p.id in self.routes
            ],
            "output_levels": {p.id: bool(outputs.get(p.id, False)) for p in OUTPUTS},
            "input_levels": inputs,
        }
