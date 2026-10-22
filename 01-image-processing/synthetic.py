"""Original procedurally generated demo images; no third-party assets."""
from __future__ import annotations

import cv2
import numpy as np


def demo_scene(kind: str, size: int = 360) -> np.ndarray:
    """Create RGB test scenes from geometry and gradients."""
    h = w = size
    yy, xx = np.mgrid[:h, :w]

    if kind == "objects":
        brightness = (199 + 20 * xx / w - 23 * yy / h + 9 * np.sin(xx / 95)).astype(np.uint8)
        rgb = np.repeat(brightness[:, :, None], 3, axis=2)
        for row in range(3):
            for col in range(3):
                x = int((col + 0.5) * w / 3)
                y = int((row + 0.5) * h / 3)
                cv2.circle(rgb, (x, y), 21 + (row + col) % 3, (50, 64, 79), -1)
                cv2.circle(rgb, (x, y), 7, (162, 173, 183), -1)
        return rgb

    if kind == "colors":
        rgb = np.empty((h, w, 3), dtype=np.uint8)
        sky = np.clip(180 + yy / h * 30, 0, 255).astype(np.uint8)
        rgb[:, :, 0] = 75
        rgb[:, :, 1] = sky
        rgb[:, :, 2] = 231
        cv2.fillPoly(rgb, [np.array([[0, h//2], [w//3, h//3], [w//2, h//2], [w, h//4], [w, h]], np.int32)], (70, 139, 89))
        cv2.fillPoly(rgb, [np.array([[0, int(h*.75)], [w, int(h*.65)], [w, h], [0, h]], np.int32)], (197, 141, 80))
        cv2.circle(rgb, (int(w*.78), int(h*.18)), int(h*.07), (255, 225, 112), -1)
        # Fine color texture makes quantization visibly different from the input.
        rng = np.random.default_rng(31)
        texture = rng.normal(0, 7, (h, w, 1))
        return np.clip(rgb.astype(np.float32) + texture, 0, 255).astype(np.uint8)

    base = 160 + 17 * np.sin(xx / (w / 4)) + 12 * yy / h
    gray = np.clip(base, 0, 255).astype(np.uint8)
    cv2.circle(gray, (int(w*.27), int(h*.34)), int(w*.16), 93, -1)
    cv2.rectangle(gray, (int(w*.52), int(h*.53)), (int(w*.84), int(h*.83)), 209, -1)
    cv2.line(gray, (int(w*.06), int(h*.88)), (int(w*.87), int(h*.13)), 116, 7)
    cv2.circle(gray, (int(w*.27), int(h*.34)), int(w*.07), 175, -1)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
