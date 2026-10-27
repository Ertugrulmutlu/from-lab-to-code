"""Integration tests for the user-facing listening workflow."""
from io import BytesIO
from pathlib import Path
import sys
import unittest
import wave

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audio_pipeline import SceneSource, render_scene
from binaural import wav_bytes
from synthetic import SAMPLE_RATE, demo_instrument


class SceneIntegrationTests(unittest.TestCase):
    def test_one_source_dimensions(self):
        tone = demo_instrument("guitar", seconds=.12)
        scene = render_scene([SceneSource("A", tone, 90)])
        self.assertEqual(len(scene.source_results), 1)
        self.assertEqual(scene.mono.shape, (len(scene.stereo),))
        self.assertEqual(scene.stereo.shape[1], 2)
        self.assertGreater(scene.source_results[0].itd_ms, 0)
        self.assertLess(scene.source_results[0].ild_db, 0)

    def test_two_sources_have_independent_measurements(self):
        tone = demo_instrument("guitar", seconds=.1)
        scene = render_scene([SceneSource("A", tone, 90),
                              SceneSource("B", tone, -90, 0, -3)])
        self.assertEqual(len(scene.source_results), 2)
        self.assertGreater(scene.source_results[0].itd_ms, 0)
        self.assertLess(scene.source_results[1].itd_ms, 0)
        self.assertGreater(scene.source_results[1].ild_db, 0)

    def test_center_produces_same_stereo_channels_as_mono(self):
        tone = demo_instrument("guitar", seconds=.08)
        scene = render_scene([SceneSource("A", tone, 0)])
        np.testing.assert_allclose(scene.stereo[:, 0], scene.stereo[:, 1], atol=1e-12)
        self.assertGreater(np.max(np.abs(scene.mono)), 0)

    def test_shared_gain_is_applied_to_both_outputs(self):
        loud = np.ones(8000, dtype=float) * .85
        scene = render_scene([SceneSource("A", loud, 0, gain_db=12)], peak_limit=.90)
        self.assertLess(scene.shared_gain, 1)
        self.assertLessEqual(np.max(np.abs(scene.mono)), .900001)
        self.assertLessEqual(np.max(np.abs(scene.stereo)), .900001)
        self.assertAlmostEqual(float(scene.mono[100] / (loud[100]*10**(12/20))), scene.shared_gain)

    def test_source_gain_before_shared_scaling(self):
        tone = np.ones(80) * .01
        scene = render_scene([SceneSource("A", tone, 0, gain_db=-6)])
        self.assertAlmostEqual(scene.mono[0], tone[0] * 10**(-6/20), places=8)
        self.assertEqual(scene.shared_gain, 1.0)

    def test_binaural_wav_has_two_channels(self):
        x = demo_instrument("horns", seconds=.1)
        scene = render_scene([SceneSource("B", x, -60)])
        with wave.open(BytesIO(wav_bytes(scene.stereo)), "rb") as file:
            self.assertEqual(file.getnchannels(), 2)
            self.assertEqual(file.getframerate(), SAMPLE_RATE)

    def test_invalid_input_rejected(self):
        with self.assertRaises(ValueError):
            render_scene([])
        with self.assertRaises(ValueError):
            render_scene([SceneSource("A", np.array([np.nan, 0.0]), 0)])


if __name__ == "__main__":
    unittest.main()
