"""Idealized position and color sensors for a didactic sorting cell."""
from __future__ import annotations

COLORS = ("red", "green", "blue")
PICKUP_X = 0.72


def item_present(box: dict | None, tolerance: float = 0.025) -> bool:
    return box is not None and abs(box["x"] - PICKUP_X) <= tolerance


def identify_color(box: dict | None) -> str | None:
    if box is None or box.get("color") not in COLORS:
        return None
    return box["color"]
