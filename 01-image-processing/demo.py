"""Generate the README example figure with no downloaded images."""
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from processing import (
    add_mixed_noise, add_periodic_noise, compare_denoisers,
    detect_dark_objects, kmeans_colors, notch_filter, to_gray,
)
from synthetic import demo_scene


def as_rgb(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return np.repeat(image[:, :, None], 3, axis=2)
    return image


def generate_gallery(path: Path) -> None:
    n = 320
    shapes = demo_scene("shapes", n)
    objects = demo_scene("objects", n)
    colors = demo_scene("colors", n)
    noisy = add_mixed_noise(shapes)
    gaussian, median = compare_denoisers(noisy)
    mask, annotated, boxes, _ = detect_dark_objects(objects, 100)
    disturbed = add_periodic_noise(shapes, 12, 7, 30)
    filtered, _, _ = notch_filter(disturbed, 12, 7, 2)
    clustered, _, _ = kmeans_colors(colors, 4)

    rows = [
        ("01  DENOISING  /  Median filter", noisy, median),
        (f"02  OBJECT COUNTING  /  {len(boxes)} regions", objects, annotated),
        ("03  FOURIER  /  Notch filter", disturbed, filtered),
        ("04  K-MEANS  /  Color clusters", colors, clustered),
    ]
    pad, gap, label_h, cell_w = 30, 20, 48, 320
    width = pad * 2 + cell_w * 2 + gap
    height = pad * 2 + len(rows) * (label_h + n + gap)
    canvas = Image.new("RGB", (width, height), "#f3f5f7")
    draw = ImageDraw.Draw(canvas)
    for i, (title, before, after) in enumerate(rows):
        y = pad + i * (label_h + n + gap)
        draw.text((pad, y), title, fill="#263244")
        draw.text((pad, y + 21), "INPUT", fill="#718096")
        draw.text((pad + cell_w + gap, y + 21), "OUTPUT", fill="#718096")
        canvas.paste(Image.fromarray(as_rgb(before)), (pad, y + label_h))
        canvas.paste(Image.fromarray(as_rgb(after)), (pad + cell_w + gap, y + label_h))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)
    print(f"Gallery generated: {path}")


if __name__ == "__main__":
    generate_gallery(Path(__file__).parent / "results" / "overview.png")
