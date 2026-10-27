"""One explicit scene-rendering pipeline shared by the UI and automated tests.

The mono baseline and the spatial output receive the SAME scalar gain. This
avoids independent peak-normalization bias when comparing the two renderings.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from binaural import get_hrir, render_one
from correlation import interaural_cues
from synthetic import SAMPLE_RATE


@dataclass(frozen=True)
class SceneSource:
    label: str
    audio: np.ndarray
    azimuth: float
    elevation: float = 0.0
    gain_db: float = 0.0


@dataclass(frozen=True)
class SourceResult:
    label: str
    hrir: np.ndarray
    requested: tuple[float, float]
    actual: tuple[float, float]
    itd_ms: float
    ild_db: float
    stereo: np.ndarray


@dataclass(frozen=True)
class SceneResult:
    mono: np.ndarray  # [frames] single channel, normally played centered
    stereo: np.ndarray  # [frames, left/right]
    source_results: tuple[SourceResult, ...]
    shared_gain: float


def render_scene(
    sources: list[SceneSource] | tuple[SceneSource, ...],
    sofa_bytes: bytes | None = None,
    *,
    fs: int = SAMPLE_RATE,
    peak_limit: float = 0.93,
) -> SceneResult:
    """Render 1–2 mono sound sources with the same source gains for A/B testing.

    A single global attenuation factor is applied to BOTH outputs if either
    would otherwise clip. No separate peak-normalizing, RMS matching, limiting,
    or dynamic gain pumping is performed. The mono output is truly mono (a
    centred source when the player sends it to two identical headphone ears).
    """
    if not 1 <= len(sources) <= 2:
        raise ValueError("A scene needs one or two sources")
    if not 0.0 < peak_limit <= 1.0:
        raise ValueError("peak_limit must lie in (0,1]")

    rendered: list[SourceResult] = []
    dry: list[np.ndarray] = []
    for source in sources:
        samples = np.asarray(source.audio, dtype=np.float64)
        if samples.ndim != 1 or len(samples) < 2 or not np.all(np.isfinite(samples)):
            raise ValueError("Each source must be a non-empty finite mono signal")
        if not np.isfinite(source.gain_db) or not -50 <= source.gain_db <= 12:
            raise ValueError("Source gain must be finite and between -50 and 12 dB")
        hrir, actual = get_hrir(source.azimuth, source.elevation, sofa_bytes, fs)
        stereo = render_one(samples, hrir, source.gain_db)
        itd, ild = interaural_cues(hrir, fs)
        rendered.append(SourceResult(source.label, hrir,
                                     (source.azimuth, source.elevation), actual,
                                     itd, ild, stereo))
        dry.append(samples * 10 ** (source.gain_db / 20.0))

    length = max(len(entry.stereo) for entry in rendered)
    stereo_mix = np.zeros((length, 2), dtype=np.float64)
    mono_mix = np.zeros(length, dtype=np.float64)
    for entry, samples in zip(rendered, dry):
        stereo_mix[:len(entry.stereo)] += entry.stereo
        mono_mix[:len(samples)] += samples

    largest = max(float(np.max(np.abs(stereo_mix))), float(np.max(np.abs(mono_mix))))
    shared_gain = min(1.0, peak_limit / largest) if largest > 0 else 1.0
    return SceneResult(mono_mix * shared_gain, stereo_mix * shared_gain,
                       tuple(rendered), shared_gain)
