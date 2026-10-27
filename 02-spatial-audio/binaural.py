"""Offline binaural rendering, optional compatible SOFA files, and safe WAV I/O.

Only standard floating point processing; playback/download always produces
16-bit PCM WAV. No university audio, course files, or datasets are bundled.
"""
from __future__ import annotations

from io import BytesIO
from math import gcd
import wave

import h5py
import numpy as np
from scipy import signal
from scipy.io import wavfile

from synthetic import SAMPLE_RATE, synthetic_hrir


MAX_SECONDS = 12.0
MAX_WAV_BYTES = 12 * 1024 * 1024
MAX_SOFA_BYTES = 45 * 1024 * 1024


def _mono_normalized(samples: np.ndarray) -> np.ndarray:
    """Read integer or float PCM as float mono, without per-file gain boost."""
    data = np.asarray(samples)
    if data.ndim == 2:
        if data.shape[1] > 2:
            raise ValueError("Only mono and stereo WAV files are supported")
        data = data.astype(np.float64).mean(axis=1)
    if data.ndim != 1 or data.size < 2:
        raise ValueError("The WAV must contain audio samples")
    if np.issubdtype(samples.dtype, np.integer):
        info = np.iinfo(samples.dtype)
        if np.issubdtype(samples.dtype, np.unsignedinteger):
            data = (data.astype(float) - (info.max + 1) / 2) / ((info.max + 1) / 2)
        else:
            data = data.astype(float) / max(abs(info.min), info.max)
    elif np.issubdtype(data.dtype, np.floating):
        data = data.astype(float)
    else:
        raise ValueError("Unsupported WAV sample format")
    if not np.all(np.isfinite(data)):
        raise ValueError("Non-finite audio values are not allowed")
    return np.clip(data, -1.0, 1.0)


def read_uploaded_wav(file_bytes: bytes, target_fs: int = SAMPLE_RATE) -> np.ndarray:
    """Read mono/stereo PCM WAV, downmix, and resample to a common sample rate."""
    if len(file_bytes) > MAX_WAV_BYTES:
        raise ValueError("Upload a WAV smaller than 12 MiB")
    try:
        fs, samples = wavfile.read(BytesIO(file_bytes))
    except Exception as error:
        raise ValueError(f"Cannot decode WAV: {error}") from error
    if fs < 8000 or fs > 192000:
        raise ValueError("Expected WAV sample rate between 8 and 192 kHz")
    if len(samples) / fs > MAX_SECONDS:
        raise ValueError(f"Upload at most {MAX_SECONDS:g} seconds of audio")
    mono = _mono_normalized(samples)
    if fs != target_fs:
        factor = gcd(int(fs), int(target_fs))
        mono = signal.resample_poly(mono, target_fs // factor, fs // factor)
    return np.asarray(mono, dtype=float)


def wav_bytes(audio: np.ndarray, fs: int = SAMPLE_RATE) -> bytes:
    """Encode [samples] mono or [samples, 2] stereo to playable PCM16 WAV."""
    a = np.asarray(audio, dtype=float)
    if a.ndim not in (1, 2) or (a.ndim == 2 and a.shape[1] != 2):
        raise ValueError("Expected mono [samples] or stereo [samples, 2]")
    if not np.all(np.isfinite(a)):
        raise ValueError("Audio contains NaN or inf")
    pcm = np.rint(np.clip(a, -1.0, 1.0) * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1 if a.ndim == 1 else 2)
        wav.setsampwidth(2)
        wav.setframerate(fs)
        wav.writeframes(pcm.tobytes())
    return output.getvalue()


def _unit_vectors(azimuth: np.ndarray, elevation: np.ndarray) -> np.ndarray:
    a = np.deg2rad(azimuth)
    e = np.deg2rad(elevation)
    return np.stack([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)], axis=-1)


def hrir_from_sofa(sofa_bytes: bytes, azimuth_deg: float, elevation_deg: float,
                   target_fs: int = SAMPLE_RATE) -> tuple[np.ndarray, float, float]:
    """Nearest-direction HRIR from a compatible AES69 SOFA file.

    Supported: SimpleFreeFieldHRIR-style Data.IR [measurements,2,samples],
    SourcePosition [measurements, >=2] in spherical *degrees*, sample rate
    common across positions. Returns (HRIR[2,samples], selected_az, selected_el).

    Assumes R[0]=left, R[1]=right. No interpolation, individualized fit,
    or coordinate remapping is attempted. Consult your dataset's documentation.
    """
    if len(sofa_bytes) > MAX_SOFA_BYTES:
        raise ValueError("SOFA file must be <= 45 MiB")
    try:
        with h5py.File(BytesIO(sofa_bytes), "r") as dataset:
            if "Data.IR" not in dataset or "SourcePosition" not in dataset or "Data.SamplingRate" not in dataset:
                raise ValueError("SOFA is missing Data.IR, SourcePosition, or Data.SamplingRate")
            ir = dataset["Data.IR"]
            positions = dataset["SourcePosition"]
            if ir.ndim != 3 or ir.shape[1] != 2 or positions.ndim != 2 or positions.shape[0] != ir.shape[0] or positions.shape[1] < 2:
                raise ValueError("Only SOFA with Data.IR [M,2,N] and SourcePosition [M,2+] is supported")
            kind = positions.attrs.get("Type", "spherical")
            kind = kind.decode() if isinstance(kind, bytes) else str(kind)
            unit = positions.attrs.get("Units", "degree, degree, metre")
            unit = unit.decode() if isinstance(unit, bytes) else str(unit)
            if kind.lower() != "spherical" or "degree" not in unit.lower():
                raise ValueError("Only spherical SourcePosition in degrees is supported")
            angles = np.asarray(positions[:, :2], dtype=float)
            if not np.all(np.isfinite(angles)):
                raise ValueError("SOFA SourcePosition contains invalid values")
            # Minimize great-circle angular separation; no nearest-neighbor
            # discontinuity near the -180/180 azimuth boundary.
            request = _unit_vectors(np.array(azimuth_deg), np.array(elevation_deg))
            candidates = _unit_vectors(angles[:, 0], angles[:, 1])
            index = int(np.argmax(candidates @ request))
            selected = np.asarray(ir[index, :2, :], dtype=float)
            raw_rate = np.asarray(dataset["Data.SamplingRate"]).ravel()
            if not len(raw_rate):
                raise ValueError("SOFA has no sample rate")
            input_fs = float(raw_rate[0])
            if np.any(np.abs(raw_rate - input_fs) > 0.01):
                raise ValueError("SOFA with per-measurement sample rates not supported")
            if not np.isfinite(input_fs) or input_fs < 8000 or input_fs > 192000:
                raise ValueError("SOFA sample rate outside supported range")
            if not np.all(np.isfinite(selected)):
                raise ValueError("SOFA HRIR includes invalid samples")
            if selected.shape[1] < 2:
                raise ValueError("SOFA HRIR has too few samples")
            sampled_az, sampled_el = map(float, angles[index])
    except OSError as error:
        raise ValueError(f"Could not read SOFA file: {error}") from error
    rounded_fs = round(input_fs)
    if abs(input_fs - rounded_fs) > 1e-3:
        raise ValueError("This demo requires integer SOFA sample rates")
    if rounded_fs != target_fs:
        div = gcd(rounded_fs, target_fs)
        selected = signal.resample_poly(selected, target_fs // div, rounded_fs // div, axis=-1)
    return np.asarray(selected, dtype=float), sampled_az, sampled_el


def get_hrir(azimuth: float, elevation: float, sofa_bytes: bytes | None = None,
             fs: int = SAMPLE_RATE) -> tuple[np.ndarray, tuple[float, float]]:
    if sofa_bytes is None:
        return synthetic_hrir(azimuth, elevation, fs), (azimuth, elevation)
    hrir, sampled_az, sampled_el = hrir_from_sofa(sofa_bytes, azimuth, elevation, fs)
    return hrir, (sampled_az, sampled_el)


def render_one(mono: np.ndarray, hrir: np.ndarray, gain_db: float = 0.0) -> np.ndarray:
    """Convolve one mono source separately with left/right HRIR; return [samples,2]."""
    x, h = np.asarray(mono, dtype=float), np.asarray(hrir, dtype=float)
    if x.ndim != 1 or h.ndim != 2 or h.shape[0] != 2:
        raise ValueError("Expected mono signal and HRIR [2,N]")
    channels = [signal.oaconvolve(x, h[ear], mode="full") for ear in range(2)]
    return np.column_stack(channels) * (10.0 ** (gain_db / 20.0))


def mix_stereo(sources: list[np.ndarray], peak: float = 0.95) -> np.ndarray:
    """Pad, sum, and jointly normalize stereo to preserve relative cues."""
    if not sources:
        raise ValueError("At least one source is required")
    if any(a.ndim != 2 or a.shape[1] != 2 for a in sources):
        raise ValueError("Every source must have shape [samples,2]")
    result = np.zeros((max(len(a) for a in sources), 2), dtype=float)
    for audio in sources:
        result[:len(audio)] += audio
    maximum = np.max(np.abs(result))
    return (result / maximum * peak) if maximum > peak else result


def mix_mono(sources: list[np.ndarray], gains_db: list[float]) -> np.ndarray:
    """Plain mono benchmark to hear the effect of spatialization."""
    length = max(len(a) for a in sources)
    mixed = np.zeros(length, dtype=float)
    for audio, gain in zip(sources, gains_db):
        mixed[:len(audio)] += audio * 10.0 ** (gain / 20.0)
    maximum = np.max(np.abs(mixed))
    return mixed / maximum * 0.95 if maximum > 0.95 else mixed
