"""Unit tests for the preparatory cross-correlation and direction convention."""
import sys
import unittest
from pathlib import Path

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from correlation import cross_correlate, example_signals, interaural_cues, nonzero_peaks
from synthetic import SAMPLE_RATE, synthetic_hrir


class CorrelationTests(unittest.TestCase):
    def test_preparation_peaks(self):
        reference, shifted = example_signals()
        lags, cc = cross_correlate(reference, shifted)
        peaks = nonzero_peaks(lags, cc)
        self.assertEqual([x[0] for x in peaks], [4, 9])
        self.assertAlmostEqual(peaks[0][1], 1.0)
        self.assertAlmostEqual(peaks[1][1], 0.5)
        self.assertEqual(len(cc), 39)

    def test_reversed_sign(self):
        a, b = example_signals()
        lag, values = cross_correlate(b, a)
        self.assertEqual([x[0] for x in nonzero_peaks(lag, values)], [-9, -4])

    def test_positive_azimuth_is_left(self):
        h = synthetic_hrir(90)
        itd, ild = interaural_cues(h, SAMPLE_RATE)
        self.assertGreater(itd, 0)
        self.assertLess(ild, 0)
        self.assertLess(abs(itd - 0.63), 0.15)

    def test_negative_azimuth_is_right(self):
        h = synthetic_hrir(-90)
        itd, ild = interaural_cues(h, SAMPLE_RATE)
        self.assertLess(itd, 0)
        self.assertGreater(ild, 0)

    def test_front_equal_ears(self):
        h = synthetic_hrir(0)
        itd, ild = interaural_cues(h, SAMPLE_RATE)
        self.assertEqual(itd, 0)
        self.assertAlmostEqual(ild, 0, places=8)
        np.testing.assert_allclose(h[0], h[1])


if __name__ == "__main__":
    unittest.main()
