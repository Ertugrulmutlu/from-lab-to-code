"""Geometric 3-DOF arm: base yaw, shoulder pitch, elbow pitch.

All lengths are in metres. A planar two-link arm is rotated around the z axis.
No collision checks, torque, acceleration, or physical dynamics are modeled.
"""
from __future__ import annotations

import math

BASE_X = 0.0
BASE_Y = -0.45
SHOULDER_HEIGHT = 0.85
UPPER_ARM = 1.40
FOREARM = 1.25


def inverse_kinematics(point: tuple[float, float, float]) -> tuple[float, float, float]:
    """Calculate base yaw, shoulder pitch, elbow pitch for a reachable wrist XYZ.

    Uses one of two elbow configurations. Angles are in radians.
    Raises ValueError for geometrically unreachable positions.
    """
    x, y, z = point
    dx, dy = x - BASE_X, y - BASE_Y
    r = math.hypot(dx, dy)
    h = z - SHOULDER_HEIGHT
    cosine = (r * r + h * h - UPPER_ARM**2 - FOREARM**2) / (2 * UPPER_ARM * FOREARM)
    if cosine < -1 - 1e-8 or cosine > 1 + 1e-8:
        raise ValueError(f"Wrist target outside robot workspace: {point}")
    cosine = max(-1.0, min(1.0, cosine))
    elbow = -math.acos(cosine)
    shoulder = math.atan2(h, r) - math.atan2(FOREARM * math.sin(elbow), UPPER_ARM + FOREARM * math.cos(elbow))
    yaw = math.atan2(dy, dx)
    return yaw, shoulder, elbow


def forward_kinematics(angles: tuple[float, float, float]) -> tuple[float, float, float]:
    yaw, shoulder, elbow = angles
    r = UPPER_ARM * math.cos(shoulder) + FOREARM * math.cos(shoulder + elbow)
    z = SHOULDER_HEIGHT + UPPER_ARM * math.sin(shoulder) + FOREARM * math.sin(shoulder + elbow)
    return BASE_X + r * math.cos(yaw), BASE_Y + r * math.sin(yaw), z


def joint_positions(angles: tuple[float, float, float]) -> dict[str, list[float]]:
    yaw, shoulder, _ = angles
    r = UPPER_ARM * math.cos(shoulder)
    elbow = (BASE_X + r * math.cos(yaw), BASE_Y + r * math.sin(yaw), SHOULDER_HEIGHT + UPPER_ARM * math.sin(shoulder))
    return {
        "base": [BASE_X, BASE_Y, 0.0],
        "shoulder": [BASE_X, BASE_Y, SHOULDER_HEIGHT],
        "elbow": list(elbow),
        "wrist": list(forward_kinematics(angles)),
    }
