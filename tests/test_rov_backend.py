import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rov_backend import SimulatedBackend, make_backend, validate_action, LEGACY_DIRECTIONS, LEGACY_STATUS


class FakeRov:
    def __init__(self):
        self.calls = []
        self.stopped = 0

    def move(self, direction, speed, duration):
        self.calls.append((direction, speed))

    def stop(self):
        self.stopped += 1


class SimulatedBackendTests(unittest.TestCase):
    def test_ramp_up_then_down(self):
        rov = FakeRov()
        b = SimulatedBackend(rov=rov, total_time=4, control_frequency=1, sleep=lambda s: None)
        b.execute('forward', 'medium')
        self.assertEqual([c[0] for c in rov.calls], ['forward'] * 5)
        self.assertEqual([c[1] for c in rov.calls], [100, 200, 100, 0, 0])

    def test_stop_action(self):
        rov = FakeRov()
        b = SimulatedBackend(rov=rov, sleep=lambda s: None)
        b.execute('stop', 'stop')
        self.assertEqual(rov.calls, [])
        self.assertEqual(rov.stopped, 1)

    def test_invalid_action(self):
        with self.assertRaises(ValueError):
            validate_action('diagonal', 'low')
        with self.assertRaises(ValueError):
            validate_action('forward', 'turbo')

    def test_factory(self):
        self.assertIsInstance(make_backend('sim', rov=FakeRov()), SimulatedBackend)
        with self.assertRaises(ValueError):
            make_backend('nope')


if __name__ == "__main__":
    unittest.main()


class NewDirectionsTests(unittest.TestCase):
    def test_sim_maps_new_directions(self):
        for d, expected in (('up', 'up'), ('down', 'down'), ('turn_left', 'turn_left'), ('turn_right', 'turn_right')):
            rov = FakeRov()
            SimulatedBackend(rov=rov, total_time=2, control_frequency=1, sleep=lambda s: None).execute(d, 'low')
            self.assertEqual(rov.calls[0][0], expected)


class LegacyTokenTests(unittest.TestCase):
    def test_chinese_tokens_still_execute(self):
        from dual_brain_core import SmallBrain
        rov = FakeRov()
        brain = SmallBrain(backend=SimulatedBackend(rov=rov, total_time=2, control_frequency=1, sleep=lambda s: None),
                           settle_time=0, frame_gap=0)
        brain.capture_pair = lambda: ("x", "y")
        brain.log_decision = lambda d: None
        brain.execute_decision({"action": {"direction": "前", "speed": "low", "confidence": 0.9}})
        self.assertEqual(rov.calls[0][0], 'forward')
        self.assertEqual(brain.history[-1]["direction"], 'forward')
        self.assertEqual(LEGACY_DIRECTIONS['停'], 'stop')
        self.assertEqual(LEGACY_STATUS.get('任务完成', '任务完成'), 'done')
        self.assertEqual(LEGACY_STATUS.get('done', 'done'), 'done')
