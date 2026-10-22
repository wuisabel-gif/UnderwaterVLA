import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from image_source import ImageSource
from rov_backend import SimulatedBackend
from dual_brain_oop import DualBrainController


class StaticSource(ImageSource):
    def __init__(self):
        self.captures = 0

    def capture(self):
        self.captures += 1
        return Image.new("RGB", (4, 4), (0, 0, 255))


class FakeRov:
    def __init__(self):
        self.moves = []
        self.stops = 0

    def move(self, direction, speed, duration):
        self.moves.append(direction)

    def stop(self):
        self.stops += 1


def make_controller(decisions, planner=None):
    rov = FakeRov()
    backend = SimulatedBackend(rov=rov, total_time=2, control_frequency=1, sleep=lambda s: None)
    ctl = DualBrainController(backend=backend, image_source=StaticSource(), settle_time=0,
                              max_steps=5, use_planner=planner is not None)
    ctl.small_brain.frame_gap = 0
    queue = list(decisions)
    ctl.small_brain.call_lmstudio_api = lambda *a, **k: queue.pop(0) if queue else None
    ctl.big_brain.call_qvqmax_api_for_planning = lambda *a, **k: planner
    return ctl, rov


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_runs_until_complete(self):
        ctl, rov = make_controller([
            {"action": {"direction": "forward", "speed": "low", "confidence": 0.9}, "status": "in_progress", "step_completed": True},
            {"action": {"direction": "right", "speed": "medium", "confidence": 0.9}, "status": "in_progress"},
            {"action": {"direction": "stop", "speed": "stop"}, "status": "done"},
        ])
        self.assertTrue(ctl.run_task("go"))
        self.assertIn("forward", rov.moves)
        self.assertIn("right", rov.moves)
        self.assertGreaterEqual(rov.stops, 1)

    def test_stops_on_api_failure(self):
        ctl, rov = make_controller([None])
        self.assertFalse(ctl.run_task("go"))
        self.assertGreaterEqual(rov.stops, 1)

    def test_max_steps_guard(self):
        forever = [{"action": {"direction": "forward", "speed": "low", "confidence": 0.9}, "status": "in_progress"}] * 20
        ctl, rov = make_controller(forever)
        self.assertFalse(ctl.run_task("go"))
        self.assertEqual(rov.moves.count("forward"), 5 * 3)  # 5 actions x (2 ramp + 1 final)

    def test_low_confidence_becomes_stop(self):
        ctl, rov = make_controller([
            {"action": {"direction": "forward", "speed": "high", "confidence": 0.2}, "status": "in_progress"},
            {"action": {"direction": "forward", "speed": "high"}, "status": "in_progress"},  # missing confidence
            {"action": {"direction": "forward", "speed": "low", "confidence": 0.9}, "status": "done"},
        ])
        self.assertTrue(ctl.run_task("go"))
        self.assertEqual(rov.moves.count("forward"), 3)  # only the confident action moved
        self.assertGreaterEqual(rov.stops, 2)

    def test_history_records_executed_actions(self):
        ctl, rov = make_controller([
            {"action": {"direction": "forward", "speed": "low", "confidence": 0.9}, "status": "in_progress"},
            {"action": {"direction": "forward", "speed": "high", "confidence": 0.1}, "status": "in_progress"},  # gated
            {"action": {"direction": "stop", "speed": "stop", "confidence": 0.9}, "status": "done"},
        ])
        ctl.small_brain.history = __import__("collections").deque(maxlen=2)
        self.assertTrue(ctl.run_task("go"))
        # gated action is recorded as the stop that was actually executed; maxlen drops the first
        self.assertEqual([h["direction"] for h in ctl.small_brain.history], ["stop", "stop"])
        ctl.small_brain.call_lmstudio_api = lambda *a, **k: None
        ctl.run_task("again")
        self.assertEqual(len(ctl.small_brain.history), 0)

    def test_planner_used_when_enabled(self):
        plan = {"task_plan": [{"step": 1, "description": "x"}], "total_steps": 1}
        ctl, rov = make_controller([{"action": {"direction": "stop", "speed": "stop"}, "status": "done"}], planner=plan)
        self.assertTrue(ctl.run_task("go"))


if __name__ == "__main__":
    unittest.main()

