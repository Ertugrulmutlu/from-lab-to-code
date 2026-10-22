"""Small, self-contained classical image-processing algorithms.

All inputs are NumPy arrays. No course material, pretrained models, or
external image data is used.
"""
from __future__ import annotations

import cv2
import numpy as np


def to_gray(image: np.ndarray) -> np.ndarray:
    """Convert an RGB uint8 image to grayscale (or return existing gray)."""
    if image.ndim == 2:
        return image.astype(np.uint8)
    if image.ndim == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    raise ValueError("Expected an HxW or HxWx3 image")


def add_mixed_noise(image: np.ndarray, sigma: float = 16.0,
                    impulse_rate: float = 0.025, seed: int = 11) -> np.ndarray:
    """Add Gaussian and salt-and-pepper noise, reproducibly."""
    gray = to_gray(image)
    rng = np.random.default_rng(seed)
    noisy = np.clip(gray.astype(np.float32) + rng.normal(0, sigma, gray.shape), 0, 255)
    salt = rng.random(gray.shape)
    noisy[salt < impulse_rate / 2] = 0
    noisy[(salt >= impulse_rate / 2) & (salt < impulse_rate)] = 255
    return noisy.astype(np.uint8)


def compare_denoisers(image: np.ndarray, kernel: int = 5) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian smoothing vs. median filtering; odd kernel >=3."""
    if kernel < 3 or kernel % 2 == 0:
        raise ValueError("Kernel size must be odd and >= 3")
    gray = to_gray(image)
    gaussian = cv2.GaussianBlur(gray, (kernel, kernel), 0)
    median = cv2.medianBlur(gray, kernel)
    return gaussian, median


def detect_dark_objects(image: np.ndarray, min_area: int = 60
                        ) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int, int]], np.ndarray]:
    """Estimate uneven illumination and count dark connected regions.

    Returns (foreground mask, RGB annotated image, boxes, illumination-corrected image).
    Works best on isolated dark objects against a lighter background.
    """
    rgb = np.stack([image] * 3, axis=-1) if image.ndim == 2 else image.copy()
    gray = to_gray(rgb)
    h, w = gray.shape
    if min(h, w) < 16:
        raise ValueError("Image should be at least 16x16 pixels")
    blur_sigma = max(12.0, min(h, w) * 0.12)
    background = cv2.GaussianBlur(gray, (0, 0), blur_sigma)
    corrected = cv2.subtract(background, gray)
    _, mask = cv2.threshold(corrected, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    accepted = np.zeros_like(mask)
    annotated = rgb.copy()
    boxes: list[tuple[int, int, int, int]] = []
    for label in range(1, count):
        x, y, ww, hh, area = [int(v) for v in stats[label]]
        if area < min_area:
            continue
        boxes.append((x, y, ww, hh))
        accepted[labels == label] = 255
        cv2.rectangle(annotated, (x, y), (x + ww, y + hh), (255, 92, 50), 2)
    return accepted, annotated, boxes, corrected


def add_periodic_noise(image: np.ndarray, cycles_x: int = 12, cycles_y: int = 7,
                       amplitude: float = 32.0) -> np.ndarray:
    """Add a sinusoidal interference pattern at known FFT-bin coordinates."""
    gray = to_gray(image)
    h, w = gray.shape
    yy, xx = np.mgrid[:h, :w]
    wave = amplitude * np.cos(2 * np.pi * (cycles_x * xx / w + cycles_y * yy / h))
    return np.clip(gray.astype(float) + wave, 0, 255).astype(np.uint8)


def notch_filter(image: np.ndarray, cycles_x: int, cycles_y: int, radius: int = 3
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reject a known pair of conjugate periodic frequencies in the FFT.

    The frequency offsets are *cycles per full image*, not pixel positions.
    Returns (filtered uint8, log-magnitude FFT, notch mask).
    """
    gray = to_gray(image)
    h, w = gray.shape
    if not (0 <= abs(cycles_x) < w // 2 and 0 <= abs(cycles_y) < h // 2):
        raise ValueError("Frequency offsets must be below the Nyquist limits")
    if cycles_x == 0 and cycles_y == 0:
        raise ValueError("Cannot remove the DC component")
    spectrum = np.fft.fftshift(np.fft.fft2(gray.astype(np.float32)))
    mask = np.ones((h, w), dtype=np.float32)
    cy, cx = h // 2, w // 2
    for sign in (1, -1):
        x = (cx + sign * cycles_x) % w
        y = (cy + sign * cycles_y) % h
        cv2.circle(mask, (x, y), radius, 0, thickness=-1)
    restored = np.fft.ifft2(np.fft.ifftshift(spectrum * mask)).real
    log_spectrum = np.log1p(np.abs(spectrum))
    return np.clip(restored, 0, 255).astype(np.uint8), log_spectrum, mask


def kmeans_colors(image: np.ndarray, clusters: int = 4, seed: int = 7
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Cluster RGB pixel colors, returning recolored image, labels, proportions."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("K-means needs an RGB image")
    if not 2 <= clusters <= 8:
        raise ValueError("Choose between 2 and 8 clusters")
    pixels = image.reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(seed)
    _, labels, centers = cv2.kmeans(
        pixels, clusters, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 25, 0.2),
        5, cv2.KMEANS_PP_CENTERS,
    )
    ids = labels.reshape(image.shape[:2])
    quantized = np.clip(centers[ids], 0, 255).astype(np.uint8)
    proportions = np.bincount(ids.ravel(), minlength=clusters) / ids.size
    return quantized, ids, proportions


def mse(reference: np.ndarray, result: np.ndarray) -> float:
    """Mean squared error between two equally-sized images."""
    if reference.shape != result.shape:
        raise ValueError("Images must have the same shape")
    return float(np.mean((reference.astype(float) - result.astype(float)) ** 2))
