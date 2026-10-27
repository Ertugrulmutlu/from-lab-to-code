"""Correlation experiments matching the CE Lab 5 preparation task.

Sign convention: correlate(later, reference) returns a positive peak lag
when ``later`` contains a delayed version of ``reference``.
"""
from __future__ import annotations

import numpy as np
from scipy import signal


def example_signals(
    length: int = 20,
    reference_at: int = 5,
    first_at: int = 9,
    second_at: int = 14,
    second_amplitude: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate the impulse signals in the preparatory Jupyter example."""
    if length < 2:
        raise ValueError("Signal length must be >= 2")
    if any(not 0 <= i < length for i in (reference_at, first_at, second_at)):
        raise ValueError("Impulse indices must be inside the array")
    reference = signal.unit_impulse(length, idx=reference_at)
    shifted = (signal.unit_impulse(length, idx=first_at)
               + second_amplitude * signal.unit_impulse(length, idx=second_at))
    return reference, shifted


def cross_correlate(reference: np.ndarray, shifted: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (lags, correlation) with positive lag = shifted signal is later."""
    a, b = np.asarray(reference, dtype=float), np.asarray(shifted, dtype=float)
    if a.ndim != 1 or b.ndim != 1 or not len(a) or not len(b):
        raise ValueError("Both signals must be nonempty 1D arrays")
    correlation = signal.correlate(b, a, mode="full")
    lags = signal.correlation_lags(len(b), len(a), mode="full")
    return lags, correlation


def nonzero_peaks(lags: np.ndarray, values: np.ndarray, tolerance: float = 1e-10) -> list[tuple[int, float]]:
    """All nonzero peaks for the impulse demonstration (not general peak detection)."""
    if len(lags) != len(values):
        raise ValueError("lags and values lengths disagree")
    # For a sum of discrete impulses, every nonzero correlation entry is
    # informative; unlike find_peaks this includes the first/last lag.
    peak_indices = np.flatnonzero(np.abs(values) > tolerance)
    return [(int(lags[i]), float(values[i])) for i in peak_indices]


def interaural_cues(hrir: np.ndarray, sample_rate: int, max_lag_ms: float = 1.0) -> tuple[float, float]:
    """Approximate ITD (right relative to left, ms) and broadband ILD (right/left, dB).

    ITD uses cross-correlation of low-pass (1.5 kHz) HRIR channels; positive
    ITD means right-ear arrival is later. Lowpass before correlation follows
    the lab's recommended approach, not an individualized auditory model.
    """
    h = np.asarray(hrir, dtype=float)
    if h.ndim != 2 or h.shape[0] != 2 or h.shape[1] < 2:
        raise ValueError("Expected HRIR with shape [2, samples]")
    if sample_rate <= 0:
        raise ValueError("sample_rate must be positive")
    energy_left = np.sum(h[0] ** 2)
    energy_right = np.sum(h[1] ** 2)
    if energy_left <= 1e-18 or energy_right <= 1e-18:
        raise ValueError("Cannot estimate cues from silent channels")

    ild_db = float(10.0 * np.log10(energy_right / energy_left))
    cutoff = min(1500.0, sample_rate * 0.42)
    sos = signal.butter(4, cutoff, btype="lowpass", fs=sample_rate, output="sos")
    low_left = signal.sosfilt(sos, h[0])
    low_right = signal.sosfilt(sos, h[1])
    lags, cc = cross_correlate(low_left, low_right)
    max_lag = max(1, round(sample_rate * max_lag_ms / 1000))
    valid = np.flatnonzero(np.abs(lags) <= max_lag)
    best = int(valid[np.argmax(cc[valid])])
    itd_ms = float(lags[best] * 1000 / sample_rate)
    return itd_ms, ild_db
