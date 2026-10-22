"""Fast checks on original, generated examples."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing import (
    add_mixed_noise, add_periodic_noise, compare_denoisers,
    detect_dark_objects, kmeans_colors, mse, notch_filter,
)
from synthetic import demo_scene


class ProcessingTests(unittest.TestCase):
    def test_denoising(self):
        original = demo_scene("shapes", 256)
        noisy = add_mixed_noise(original, seed=12)
        gaussian, median = compare_denoisers(noisy)
        self.assertEqual(gaussian.shape, noisy.shape[:2])
        self.assertLess(mse(median, original[:, :, 0]), mse(noisy, original[:, :, 0]))

    def test_object_count(self):
        image = demo_scene("objects", 360)
        mask, annotated, boxes, corrected = detect_dark_objects(image, 100)
        self.assertEqual(len(boxes), 9)
        self.assertEqual(mask.shape, image.shape[:2])
        self.assertEqual(annotated.shape, image.shape)

    def test_fft_removes_generated_interference(self):
        original = demo_scene("shapes", 256)[:, :, 0]
        noisy = add_periodic_noise(original, 12, 7, 30)
        clean, log_fft, mask = notch_filter(noisy, 12, 7, 2)
        self.assertLess(mse(original, clean), mse(original, noisy))
        self.assertEqual(mask.shape, original.shape)
        self.assertEqual(log_fft.shape, original.shape)

    def test_kmeans(self):
        original = demo_scene("colors", 192)
        clustered, labels, shares = kmeans_colors(original, 4)
        self.assertEqual(clustered.shape, original.shape)
        self.assertEqual(labels.shape, original.shape[:2])
        self.assertAlmostEqual(shares.sum(), 1.0)


if __name__ == "__main__":
    unittest.main()
