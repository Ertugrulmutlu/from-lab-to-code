"""Original, deterministic audio and educational (NOT measured) HRIR filters."""
from __future__ import annotations

import numpy as np
from scipy import signal

SAMPLE_RATE = 44_100


def _fractional_impulse(length: int, offset: float, half_width: int = 12) -> np.ndarray:
    """Fractional sample delay using a windowed-sinc FIR impulse."""
    n = np.arange(length, dtype=float)
    impulse = np.sinc(n - offset)
    mask = (np.abs(n - offset) <= half_width).astype(float)
    # Smooth truncation, avoiding ringing from a rectangular sinc window.
    window = 0.5 + 0.5 * np.cos(np.pi * np.clip((n - offset) / half_width, -1, 1))
    impulse *= mask * window
    impulse /= max(1e-12, np.sum(impulse))
    return impulse


def synthetic_hrir(azimuth_deg: float, elevation_deg: float = 0, fs: int = SAMPLE_RATE) -> np.ndarray:
    """Toy HRIR: geometric ITD, head-shadow amplitude, and mild spectral coloring.

    Coordinate convention: 0 deg=front, +90 deg=left, -90 deg=right.
    Elevation coloring is illustrative, not a measurement of a real pinna.
    Returns [left, right] at the requested sample rate.
    """
    if fs < 8000:
        raise ValueError("Sample rate is too low")
    if not -90 <= elevation_deg <= 90:
        raise ValueError("Elevation must lie in [-90, 90]")
    if not -180 <= azimuth_deg <= 180:
        raise ValueError("Azimuth must lie in [-180, 180]")
    # Signed arrival difference (right time - left time).
    lateral = np.sin(np.deg2rad(azimuth_deg)) * np.cos(np.deg2rad(elevation_deg))
    delay_samples = 0.00063 * fs * lateral
    near_delay = 15.0
    left_delay = near_delay + max(0.0, -delay_samples)
    right_delay = near_delay + max(0.0, delay_samples)
    length = max(128, int(max(left_delay, right_delay)) + 36)
    left = _fractional_impulse(length, left_delay)
    right = _fractional_impulse(length, right_delay)

    # Far ear attenuated up to ~12 dB at the lateral extremes.
    shadow_gain = 10.0 ** (-12.0 * abs(lateral) / 20.0)
    if lateral > 0:
        right *= shadow_gain
        right = signal.lfilter([0.67, 0.0], [1.0, -0.33], right)
    elif lateral < 0:
        left *= shadow_gain
        left = signal.lfilter([0.67, 0.0], [1.0, -0.33], left)

    # Both ears receive subtle elevation-dependent spectral coloration.
    # This is NOT a genuine HRTF:  elevation and front/back remain ambiguous.
    color = 0.12 * np.sin(np.deg2rad(elevation_deg))
    fir = np.array([1.0, -color, 0.0, color / 2.0])
    left = signal.lfilter(fir, [1.0], left)
    right = signal.lfilter(fir, [1.0], right)
    return np.stack([left, right])


def demo_instrument(kind: str, fs: int = SAMPLE_RATE, seconds: float = 3.0) -> np.ndarray:
    """Fully synthetic, original samples: plucked notes or harmonic brass-like tones."""
    count = int(fs * seconds)
    audio = np.zeros(count, dtype=float)
    if kind == "guitar":
        notes = [196.0, 246.94, 293.66, 392.0, 329.63, 246.94]
        for i, frequency in enumerate(notes):
            start = int((i * 0.45) * fs)
            duration = min(int(0.85 * fs), count - start)
            if duration <= 0:
                break
            t = np.arange(duration, dtype=float) / fs
            pluck = (np.sin(2 * np.pi * frequency * t)
                     + 0.35 * np.sin(2 * np.pi * frequency * 2 * t)
                     + 0.18 * np.sin(2 * np.pi * frequency * 3 * t))
            envelope = (1.0 - np.exp(-t * 220)) * np.exp(-t * 4.3)
            audio[start:start + duration] += pluck * envelope
    elif kind == "horns":
        t = np.arange(count, dtype=float) / fs
        phase = 2 * np.pi * (164.81 * t + 3.0 * t**2)
        wave = (np.sin(phase)
                + 0.5 * np.sin(2 * phase + 0.1)
                + 0.25 * np.sin(3 * phase)
                + 0.12 * np.sin(4 * phase))
        attack = 1 - np.exp(-t * 7)
        release = np.minimum(1.0, np.maximum(0.0, (seconds - t) * 3))
        audio = wave * attack * release * (0.8 + 0.2 * np.sin(2 * np.pi * 2.3 * t))
    else:
        raise ValueError(f"Unknown demo instrument: {kind}")
    audio *= 0.6 / max(np.max(np.abs(audio)), 1e-12)
    return audio
