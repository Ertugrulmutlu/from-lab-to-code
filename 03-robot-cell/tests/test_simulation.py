import math
import unittest

from robotics.kinematics import forward_kinematics, inverse_kinematics
from robotics.sensors import identify_color, item_present
from robotics.simulation import BINS, HOME, PICKUP, RobotCell


class KinematicsTests(unittest.TestCase):
    def test_inverse_forward_round_trip(self):
        targets = [HOME, PICKUP, (0.72, 1.05, 1.44), *BINS.values()]
        for target in targets:
            with self.subTest(target=target):
                xyz = forward_kinematics(inverse_kinematics(target))
                for actual, expected in zip(xyz, target):
                    self.assertAlmostEqual(actual, expected, places=6)

    def test_unreachable_target_rejected(self):
        with self.assertRaises(ValueError):
            inverse_kinematics((10.0, 10.0, 10.0))


class SensorsTests(unittest.TestCase):
    def test_ideal_sensor_detection(self):
        self.assertTrue(item_present({"x": 0.72}))
        self.assertFalse(item_present({"x": -0.3}))
        self.assertEqual(identify_color({"color": "blue"}), "blue")
        self.assertIsNone(identify_color({"color": "purple"}))


class CellTests(unittest.TestCase):
    def test_paused_simulation_does_not_advance(self):
        sim = RobotCell()
        sim.step(0.1)
        self.assertEqual(sim.phase, "IDLE")
        self.assertEqual(sim.elapsed, 0)

    def test_full_sorting_cycle_for_each_color(self):
        for color in ("red", "green", "blue"):
            with self.subTest(color=color):
                sim = RobotCell()
                sim.configure(color=color)
                sim.run()
                for _ in range(600):
                    sim.step(0.08)
                    if sim.pick_count:
                        break
                self.assertEqual(sim.pick_count, 1)
                self.assertEqual(sim.counts[color], 1)
                self.assertFalse(sim.gripping)

    def test_speed_and_color_input_validation(self):
        sim = RobotCell()
        for bad in (0, 3.5, float("nan"), True):
            with self.assertRaises(ValueError):
                sim.configure(speed=bad)
        with self.assertRaises(ValueError):
            sim.configure(color="orange")

    def test_reset_restarts_counts_and_state(self):
        sim = RobotCell()
        sim.run()
        sim.step(0.08)
        sim.reset()
        self.assertEqual(sim.phase, "IDLE")
        self.assertEqual(sim.pick_count, 0)
        self.assertIsNone(sim.box)
        self.assertFalse(sim.running)


if __name__ == "__main__":
    unittest.main()
