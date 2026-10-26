import configparser
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "QGC"))
try:
    import numpy  # noqa: F401
except ImportError:
    sys.modules["numpy"] = types.ModuleType("numpy")

import sim_horizon
from auto_controller import MPCController


def cfg():
    c = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    c.read(os.path.join(ROOT, "QGC", "config.ini"), encoding="utf-8")
    return c


class ProfileScalesWithHorizon(unittest.TestCase):
    def test_profile_fills_horizon(self):
        for h in (0.5, 1.0, 2.0):
            m = MPCController(cfg())
            m.control_horizon, m.steps = h, int(h / m.control_interval)
            m.set_vla_command("forward", "high")
            prof = m.reference_profile
            self.assertEqual(len(prof), int(h / 0.02))
            self.assertAlmostEqual(max(prof), 0.8)
            self.assertAlmostEqual(prof[int(len(prof) * 0.3)], 0.8)   # cruising at 30% of the horizon
            self.assertLess(prof[-1], 0.1)                             # ramped down by the end


class SimTests(unittest.TestCase):
    def test_arrives_and_longer_horizon_needs_fewer_decisions(self):
        c = cfg()
        r1 = sim_horizon.run(1.0, 0.0, 5.0, c)
        r3 = sim_horizon.run(3.0, 0.0, 5.0, c)
        for r in (r1, r3):
            self.assertLess(abs(r["error"]), sim_horizon.TOL)
        self.assertLess(r3["decisions"], r1["decisions"])

    def test_latency_adds_time(self):
        c = cfg()
        self.assertGreater(sim_horizon.run(1.0, 2.0, 5.0, c)["time"], sim_horizon.run(1.0, 0.0, 5.0, c)["time"])


if __name__ == "__main__":
    unittest.main()
