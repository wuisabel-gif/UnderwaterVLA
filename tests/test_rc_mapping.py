import os
import sys
import types
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'QGC'))

for name in ('numpy',):
    try:
        __import__(name)
    except ImportError:
        sys.modules[name] = types.ModuleType(name)
if 'pymavlink' not in sys.modules:
    try:
        import pymavlink  # noqa: F401
    except ImportError:
        pm = types.ModuleType('pymavlink')
        pm.mavutil = types.SimpleNamespace()
        pm.mavwp = types.SimpleNamespace()
        sys.modules['pymavlink'] = pm
        sys.modules['pymavlink.mavutil'] = pm.mavutil
        sys.modules['pymavlink.mavwp'] = pm.mavwp

from mavlink_interface import MavlinkInterface
from auto_controller import AutoController

CONFIG = os.path.join(ROOT, 'QGC', 'config.ini')


class RcMappingTests(unittest.TestCase):
    def test_channel_order_matches_ardusub(self):
        mi = MavlinkInterface(CONFIG)
        mi.is_connected = True
        mi.mavlink_connection = mock.MagicMock(target_system=1, target_component=1)
        mi.send_manual_control(roll=0.2, pitch=-0.4, throttle=0.6, yaw=-0.8, forward=1.0, lateral=-1.0)
        args = mi.mavlink_connection.mav.rc_channels_override_send.call_args[0]
        # (sys, comp, ch1 pitch, ch2 roll, ch3 throttle, ch4 yaw, ch5 forward, ch6 lateral, ch7, ch8)
        self.assertEqual(args[2:], (1300, 1600, 1800, 1100, 2000, 1000, 65535, 65535))

    def test_mpc_forward_thrust_goes_to_forward_not_throttle(self):
        ac = AutoController(CONFIG)
        ac.enable_depth_hold = False
        ac.enable_heading_hold = False
        ac.mpc_controller.is_active = True
        ac.mpc_controller.compute_control = lambda: {'forward': 0.5, 'lateral': 0.0, 'throttle': 0.0, 'yaw': 0.0}
        ac._safety_check = lambda: None
        ac._execute_auto_control()
        self.assertAlmostEqual(ac.control_outputs['forward'], 0.5)
        self.assertAlmostEqual(ac.control_outputs['throttle'], 0.0)

    def test_depth_hold_uses_vertical_throttle(self):
        ac = AutoController(CONFIG)
        ac.enable_heading_hold = False
        ac.target_depth, ac._current_depth = -2.0, 0.0
        ac._safety_check = lambda: None
        ac._execute_auto_control()
        self.assertLess(ac.control_outputs['throttle'], 0.0)   # push down
        self.assertAlmostEqual(ac.control_outputs['pitch'], 0.0)


if __name__ == "__main__":
    unittest.main()


class ActionAxisTests(unittest.TestCase):
    def axis_for(self, direction):
        ac = AutoController(CONFIG)
        ac.enable_depth_hold = ac.enable_heading_hold = False
        ac._safety_check = lambda: None
        ac.mpc_controller.set_vla_command(direction, 'medium')
        m = ac.mpc_controller  # profile ramps from 0, so key off the commanded target sign
        m._compute_translational_control = lambda ref: 0.7 * (m.target_velocity > 0) - 0.7 * (m.target_velocity < 0)
        m._compute_rotational_control = lambda ref: 0.9 if m.target_angular_rate > 0 else -0.9
        ac._execute_auto_control()
        return {k: v for k, v in ac.control_outputs.items() if v}

    def test_each_direction_hits_one_axis(self):
        self.assertEqual(self.axis_for('前'), {'forward': 0.7})
        self.assertEqual(self.axis_for('后'), {'forward': -0.7})
        self.assertEqual(self.axis_for('右'), {'lateral': 0.7})
        self.assertEqual(self.axis_for('左'), {'lateral': -0.7})
        self.assertEqual(self.axis_for('上'), {'throttle': 0.7})
        self.assertEqual(self.axis_for('下'), {'throttle': -0.7})
        self.assertEqual(self.axis_for('右转'), {'yaw': 0.9})
        self.assertEqual(self.axis_for('左转'), {'yaw': -0.9})
        self.assertEqual(self.axis_for('停'), {})
