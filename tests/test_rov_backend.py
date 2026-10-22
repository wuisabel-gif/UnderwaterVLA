import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rov_backend import SimulatedBackend, make_backend, validate_action


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
        b.execute('前', 'medium')
        self.assertEqual([c[0] for c in rov.calls], ['forward'] * 5)
        self.assertEqual([c[1] for c in rov.calls], [100, 200, 100, 0, 0])

    def test_stop_action(self):
        rov = FakeRov()
        b = SimulatedBackend(rov=rov, sleep=lambda s: None)
        b.execute('停', 'stop')
        self.assertEqual(rov.calls, [])
        self.assertEqual(rov.stopped, 1)

    def test_invalid_action(self):
        with self.assertRaises(ValueError):
            validate_action('斜', 'low')
        with self.assertRaises(ValueError):
            validate_action('前', 'turbo')

    def test_factory(self):
        self.assertIsInstance(make_backend('sim', rov=FakeRov()), SimulatedBackend)
        with self.assertRaises(ValueError):
            make_backend('nope')


if __name__ == "__main__":
    unittest.main()


class NewDirectionsTests(unittest.TestCase):
    def test_sim_maps_new_directions(self):
        for d, expected in (('上', 'up'), ('下', 'down'), ('左转', 'turn_left'), ('右转', 'turn_right')):
            rov = FakeRov()
            SimulatedBackend(rov=rov, total_time=2, control_frequency=1, sleep=lambda s: None).execute(d, 'low')
            self.assertEqual(rov.calls[0][0], expected)
