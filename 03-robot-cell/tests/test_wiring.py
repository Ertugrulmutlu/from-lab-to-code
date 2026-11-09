"""Functional tests for disconnected and deliberately miswired digital I/O."""
import unittest

from robotics.io import DEFAULT_CONNECTIONS, IOBoard
from robotics.simulation import RobotCell, SPAWN_X, PICKUP_X


def run_until(cell, predicate, max_steps=700):
    for _ in range(max_steps):
        cell.step(0.08)
        if predicate(cell):
            return
    raise AssertionError(f"Timeout in phase={cell.phase}; diagnostic={cell.state()['diagnostic']}")


class BoardTests(unittest.TestCase):
    def test_default_wiring_routes_all_ten_inputs(self):
        board = IOBoard()
        self.assertEqual(board.routes, DEFAULT_CONNECTIONS)
        result = board.resolve({"Robot.StartStop": True, "PositionSensor.Detect": True})
        self.assertTrue(result["Belt.OnOff"])
        self.assertTrue(result["Robot.ItemAvailable"])
        self.assertFalse(result["Gripper.Vacuum"])

    def test_validates_port_directions(self):
        board = IOBoard()
        for source, target in (
            ("Robot.ItemAvailable", "Belt.OnOff"),  # input -> input
            ("Robot.StartStop", "Robot.Generate"),  # output -> output
            ("unknown", "Belt.OnOff"),
            ("Robot.StartStop", "unknown"),
        ):
            with self.subTest(source=source, target=target):
                with self.assertRaises(ValueError):
                    board.connect(source, target)
        self.assertEqual(board.routes, DEFAULT_CONNECTIONS)

    def test_disconnect_and_restore(self):
        board = IOBoard()
        board.disconnect("Belt.OnOff")
        self.assertFalse(board.resolve({"Robot.StartStop": True})["Belt.OnOff"])
        board.restore()
        self.assertEqual(board.routes, DEFAULT_CONNECTIONS)


class WiringIntegrationTests(unittest.TestCase):
    def test_unplug_source_prevents_creation(self):
        cell = RobotCell()
        cell.edit_wiring("disconnect", input_="Source.Trigger")
        cell.run()
        for _ in range(60):
            cell.step(0.08)
        self.assertEqual(cell.phase, "IDLE")
        self.assertIsNone(cell.box)
        self.assertIn("Source.Trigger", cell.state()["diagnostic"])

    def test_unplug_belt_stops_box_at_start(self):
        cell = RobotCell()
        cell.edit_wiring("preset", preset="missing_belt")
        cell.configure(color="green")
        cell.run()
        for _ in range(70):
            cell.step(0.08)
        self.assertEqual(cell.phase, "CONVEYING")
        self.assertAlmostEqual(cell.box["x"], SPAWN_X)
        self.assertIn("Belt.OnOff", cell.state()["diagnostic"])
        self.assertTrue(cell.state()["wiring"]["output_levels"]["Robot.StartStop"])
        self.assertFalse(cell.state()["wiring"]["input_levels"]["Belt.OnOff"])

    def test_unplug_position_sensor_stalls_at_pickup(self):
        cell = RobotCell()
        cell.edit_wiring("preset", preset="missing_position")
        cell.run()
        run_until(cell, lambda c: c.box is not None and c.box["x"] == PICKUP_X)
        self.assertEqual(cell.phase, "CONVEYING")
        self.assertIn("position sensor", cell.state()["diagnostic"])

    def test_unplug_gripper_causes_fault_at_pick(self):
        cell = RobotCell()
        cell.edit_wiring("preset", preset="missing_gripper")
        cell.run()
        run_until(cell, lambda c: c.phase == "FAULT")
        self.assertFalse(cell.running)
        self.assertIn("Vacuum", cell.fault)
        self.assertEqual(cell.pick_count, 0)
        with self.assertRaises(ValueError):
            cell.run()

    def test_unplug_sink_causes_fault_on_drop(self):
        cell = RobotCell()
        cell.configure(color="red")
        cell.edit_wiring("disconnect", input_="RedSink.Remove")
        cell.configure(color="red")
        cell.run()
        run_until(cell, lambda c: c.phase == "FAULT")
        self.assertIn("sink", cell.fault)
        self.assertEqual(cell.pick_count, 0)

    def test_swapped_color_sensors_cause_real_missort(self):
        cell = RobotCell()
        cell.edit_wiring("preset", preset="swapped_colors")
        cell.configure(color="red")
        cell.run()
        run_until(cell, lambda c: c.missorted > 0)
        self.assertEqual(cell.missorted, 1)
        self.assertEqual(cell.pick_count, 0)
        self.assertEqual(cell.counts["red"], 0)
        self.assertEqual(cell.bin_contents["blue"]["red"], 1)
        self.assertTrue(any("MIS-SORTED" in e["message"] for e in cell.events))

    def test_wiring_edit_requires_pause_and_resets_cycle(self):
        cell = RobotCell()
        cell.run()
        with self.assertRaises(ValueError):
            cell.edit_wiring("disconnect", input_="Belt.OnOff")
        self.assertIn("Belt.OnOff", cell.io.routes)
        cell.pause()
        cell.edit_wiring("disconnect", input_="Belt.OnOff")
        self.assertEqual(cell.phase, "IDLE")
        self.assertFalse(cell.running)
        self.assertNotIn("Belt.OnOff", cell.io.routes)
        cell.reset()
        self.assertNotIn("Belt.OnOff", cell.io.routes)  # simulation reset keeps wiring
        cell.edit_wiring("restore")
        self.assertEqual(cell.io.routes, DEFAULT_CONNECTIONS)

    def test_invalid_preset_rejected_without_reset(self):
        cell = RobotCell()
        with self.assertRaises(ValueError):
            cell.edit_wiring("preset", preset="unknown")
        self.assertEqual(cell.io.routes, DEFAULT_CONNECTIONS)


if __name__ == "__main__":
    unittest.main()
