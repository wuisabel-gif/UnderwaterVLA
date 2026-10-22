import os
import sys
import unittest
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'QGC'))

# auto_controller imports numpy at module level; stub it if absent
try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules['numpy'] = types.ModuleType('numpy')

from auto_controller import AutoController


class SafetyCheckTests(unittest.TestCase):
    def make(self):
        ac = AutoController(os.path.join(ROOT, 'QGC', 'config.ini'))
        ac.max_depth, ac.min_depth = -10.0, -0.5
        ac.control_outputs = {'roll': 0.3, 'pitch': 0.0, 'throttle': 0.5, 'yaw': 0.0}
        return ac

    def test_surface_does_not_trigger_emergency_stop(self):
        ac = self.make()
        ac._current_depth = 0.0
        ac._safety_check()
        self.assertEqual(ac.control_outputs['throttle'], 0.5)
        self.assertEqual(ac.emergency_stop_time, 0)

    def test_too_deep_triggers_emergency_stop(self):
        ac = self.make()
        ac._current_depth = -11.0
        ac._safety_check()
        self.assertEqual(ac.control_outputs['throttle'], 0.0)
        self.assertNotEqual(ac.emergency_stop_time, 0)


if __name__ == "__main__":
    unittest.main()
