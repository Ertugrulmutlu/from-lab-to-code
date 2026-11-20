import unittest

from robot_lab.physics import Plant
from robot_lab.simulation import Settings, Simulator, compare


class PhysicsTests(unittest.TestCase):
    def test_acceleration_and_brake(self):
        plant = Plant()
        plant.command_speed(6)
        for _ in range(100):
            plant.step(0.01)
        self.assertAlmostEqual(plant.speed, 3, places=5)
        self.assertAlmostEqual(plant.odometer, 1.5, places=4)
        plant.brake()
        for _ in range(100):
            plant.step(0.01)
        self.assertEqual(plant.speed, 0)
        self.assertFalse(plant.collided)

    def test_wall_collision_at_robot_radius(self):
        plant = Plant(x=50, wall_x=52, radius=1, speed=5, desired_speed=5)
        plant.step(.3)
        self.assertTrue(plant.collided)
        self.assertEqual(plant.x, 51)
        self.assertEqual(plant.gap, 0)

    def test_no_negative_speed_after_braking(self):
        plant = Plant(speed=.01, desired_speed=0)
        plant.step(.1)
        self.assertEqual(plant.speed, 0)


class ControllerTests(unittest.TestCase):
    def test_default_async_stops_safely(self):
        data = Simulator(Settings(), 'async').run()
        self.assertEqual(data['result'], 'safe_stop')
        self.assertGreater(data['metrics']['final_clearance_m'], 0)
        self.assertGreater(data['metrics']['samples_received'], 15)
        self.assertIsNotNone(data['controller']['brake_applied_at'])

    def test_blocking_can_collide_under_identical_conditions(self):
        data = compare(Settings(network_rtt_ms=50, jitter_ms=20, seed=2026))
        self.assertEqual(data['async']['result'], 'safe_stop')
        self.assertEqual(data['blocking']['result'], 'collision')
        self.assertGreater(data['blocking']['metrics']['control_ticks_blocked'], 0)
        self.assertEqual(data['async']['metrics']['control_ticks_blocked'], 0)

    def test_virtual_network_is_reproducible(self):
        conf = Settings(target_speed=12, network_rtt_ms=160, jitter_ms=120, seed=91)
        self.assertEqual(compare(conf), compare(conf))

    def test_start_stop_honors_same_geometry(self):
        for mode in ('blocking','async'):
            simulation = Simulator(Settings(network_rtt_ms=0,jitter_ms=0),mode)
            self.assertEqual(simulation.plant.x,8)
            self.assertEqual(simulation.plant.wall_x,52)
            self.assertEqual(simulation.plant.radius,1)
            simulation.run()
            self.assertTrue(simulation.finished)
            self.assertIn(simulation.result, ('safe_stop','collision'))

    def test_pause_by_not_advancing(self):
        sim=Simulator()
        state=sim.step(12)
        self.assertEqual(sim.now,0.12)
        self.assertEqual(sim.snapshot(),state)

    def test_validation_rejects_invalid_values(self):
        with self.assertRaises(ValueError): Settings(braking=0).validated()
        with self.assertRaises(ValueError): Settings(jitter_ms=1000).validated()
        with self.assertRaises(ValueError): Simulator(mode='telepathy')

    def test_sensor_sample_times_are_ordered(self):
        sim=Simulator(Settings(network_rtt_ms=100, jitter_ms=150, seed=13))
        sim.step(300)
        self.assertIsNotNone(sim.latest_sample_time)
        self.assertGreater(sim.samples_received, 0)
        self.assertGreater(sim.requests_sent, sim.samples_received)


if __name__ == '__main__':
    unittest.main()
