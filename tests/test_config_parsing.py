import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'QGC'))

try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules['numpy'] = types.ModuleType('numpy')

from auto_controller import AutoController


class ConfigParsingTests(unittest.TestCase):
    def test_config_with_inline_comments_loads(self):
        ac = AutoController(os.path.join(ROOT, 'QGC', 'config.ini'))
        self.assertEqual(ac.control_frequency, 10)
        self.assertAlmostEqual(ac.target_depth, -2.0)
        self.assertAlmostEqual(ac.max_depth, -10.0)


if __name__ == "__main__":
    unittest.main()
