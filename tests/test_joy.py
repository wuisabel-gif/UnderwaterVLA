import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'QGC'))

# pyvjoy is Windows-only; fake the bits joy.py touches
pyvjoy = types.ModuleType('pyvjoy')
for i, name in enumerate(('X', 'Y', 'Z', 'RX', 'RY', 'RZ')):
    setattr(pyvjoy, f'HID_USAGE_{name}', i)


class FakeDevice:
    def __init__(self, _id):
        self.axes = {}

    def reset(self):
        self.axes = {}

    def update(self):
        pass

    def set_axis(self, axis, value):
        self.axes[axis] = value

    def set_button(self, *_):
        pass


pyvjoy.VJoyDevice = FakeDevice
sys.modules['pyvjoy'] = pyvjoy

import joy


class JoyTests(unittest.TestCase):
    def nonzero_axes(self, direction, speed='high'):
        c = joy.VJoyController()
        c.execute_from_json({"action": {"direction": direction, "speed": speed}})
        return {a: v for a, v in c.device.axes.items() if v != 16384}  # 16384 == centred

    def test_every_direction_drives_one_axis(self):
        self.assertEqual(self.nonzero_axes('forward'), {pyvjoy.HID_USAGE_Y: 0})
        self.assertEqual(self.nonzero_axes('backward'), {pyvjoy.HID_USAGE_Y: 32768})
        self.assertEqual(self.nonzero_axes('left'), {pyvjoy.HID_USAGE_X: 0})
        self.assertEqual(self.nonzero_axes('up'), {pyvjoy.HID_USAGE_Z: 0})
        self.assertEqual(self.nonzero_axes('down'), {pyvjoy.HID_USAGE_Z: 32768})
        self.assertEqual(self.nonzero_axes('turn_left'), {pyvjoy.HID_USAGE_RX: 0})
        self.assertEqual(self.nonzero_axes('turn_right'), {pyvjoy.HID_USAGE_RX: 32768})
        self.assertEqual(self.nonzero_axes('stop'), {})

    def test_speed_scales(self):
        self.assertEqual(self.nonzero_axes('right', 'low'), {pyvjoy.HID_USAGE_X: int(1.3 * 16384)})

    def test_invalid_rejected(self):
        with self.assertRaises(ValueError):
            joy.VJoyController().execute_from_json({"action": {"direction": "sideways", "speed": "low"}})


if __name__ == "__main__":
    unittest.main()
