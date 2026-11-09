import unittest

try:
    import app as backend
except ImportError:
    backend = None


@unittest.skipIf(backend is None, "Install Flask to run API tests")
class APITests(unittest.TestCase):
    def setUp(self):
        self.client = backend.app.test_client()
        with backend.lock:
            backend.cell.pause()
            backend.cell.edit_wiring("restore")

    def test_state_endpoint(self):
        r = self.client.get("/api/state")
        self.assertEqual(r.status_code, 200)
        self.assertIn("robot", r.json)

    def test_run_and_tick(self):
        self.client.post("/api/control", json={"action": "run"})
        r = self.client.post("/api/step", json={"dt": 0.08})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json["phase"], "CONVEYING")

    def test_connection_endpoints(self):
        r = self.client.post("/api/wiring", json={"action": "disconnect", "input": "Belt.OnOff"})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("Belt.OnOff", [c["input"] for c in r.json["wiring"]["connections"]])
        r = self.client.post("/api/wiring", json={"action": "connect", "output": "Robot.StartStop", "input": "Belt.OnOff"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(c["input"] == "Belt.OnOff" for c in r.json["wiring"]["connections"]))

    def test_wiring_change_rejected_when_running(self):
        self.client.post("/api/control", json={"action": "run"})
        r = self.client.post("/api/wiring", json={"action": "disconnect", "input": "Belt.OnOff"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Pause", r.json["error"])

    def test_reject_invalid_wiring_ports_and_presets(self):
        r = self.client.post("/api/wiring", json={"action": "connect", "output": "Robot.ItemAvailable", "input": "Robot.Generate"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/wiring", json={"action": "preset", "preset": "incorrect"})
        self.assertEqual(r.status_code, 400)

    def test_invalid_values_fail_cleanly(self):
        r = self.client.post("/api/control", json={"action": "configure", "speed": 99})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/api/step", json={"dt": "invalid"})
        self.assertEqual(r.status_code, 400)


if __name__ == "__main__":
    unittest.main()
