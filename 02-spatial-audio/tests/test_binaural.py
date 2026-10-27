"""Audio export, convolution, and compatible SOFA reader sanity checks."""
from io import BytesIO
import sys
import unittest
from pathlib import Path
import wave

import h5py
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from binaural import (get_hrir, hrir_from_sofa, mix_mono, mix_stereo,
                      read_uploaded_wav, render_one, wav_bytes)
from synthetic import SAMPLE_RATE, demo_instrument, synthetic_hrir


class BinauralTests(unittest.TestCase):
    def test_demo_signals_are_own_and_finite(self):
        for instrument in ("guitar", "horns"):
            x = demo_instrument(instrument, seconds=1.0)
            self.assertEqual(len(x), SAMPLE_RATE)
            self.assertTrue(np.isfinite(x).all())
            self.assertLessEqual(np.max(np.abs(x)), 1.0)

    def test_stereo_convolution_and_wav_header(self):
        mono = demo_instrument("guitar", seconds=0.2)
        hrir = synthetic_hrir(45)
        result = render_one(mono, hrir)
        self.assertEqual(result.shape, (len(mono) + hrir.shape[1] - 1, 2))
        bytes_data = wav_bytes(mix_stereo([result]))
        with wave.open(BytesIO(bytes_data), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 2)
            self.assertEqual(audio.getframerate(), SAMPLE_RATE)

    def test_uploaded_wav_decode(self):
        src = np.sin(2 * np.pi * 440 * np.arange(3200) / 16000)
        wav = wav_bytes(src, fs=16000)
        out = read_uploaded_wav(wav)
        self.assertEqual(len(out), 8820)
        self.assertLessEqual(np.max(np.abs(out)), 1.1)

    def test_mono_mix(self):
        x = np.ones(4) * 0.1
        mix = mix_mono([x, x], [0, -6])
        self.assertEqual(mix.shape, (4,))

    def test_nearest_sofa_direction(self):
        # Tiny, fully synthetic SOFA fixture entirely in memory (not an external dataset).
        memory = BytesIO()
        with h5py.File(memory, "w") as f:
            ir = np.zeros((2, 2, 48))
            ir[0, :, 4] = 1.0
            ir[1, :, 7] = 1.0
            f.create_dataset("Data.IR", data=ir)
            f.create_dataset("Data.SamplingRate", data=[44100.0])
            pos = f.create_dataset("SourcePosition", data=np.array([[0, 0, 1], [90, 0, 1]]))
            pos.attrs["Type"] = "spherical"
            pos.attrs["Units"] = "degree, degree, metre"
        sofa_data = memory.getvalue()
        h, az, el = hrir_from_sofa(sofa_data, 80, 0)
        self.assertEqual((az, el), (90.0, 0.0))
        self.assertEqual(int(np.argmax(h[0])), 7)
        wrapped, nearest = get_hrir(80, 0, sofa_data)
        self.assertEqual(nearest, (90.0, 0.0))
        np.testing.assert_allclose(wrapped, h)

    def test_unreadable_sofa_file(self):
        with self.assertRaises(ValueError):
            hrir_from_sofa(b"nonsense", 0, 0)


if __name__ == "__main__":
    unittest.main()
