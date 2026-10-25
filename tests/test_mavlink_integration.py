"""
Drives ArduSubBackend over a real MAVLink UDP link against a fake vehicle.

The fake vehicle sends heartbeats and attitude like ArduSub would and records every
RC_CHANNELS_OVERRIDE it receives. No ArduPilot build needed; skipped if pymavlink
is not installed.
"""
import configparser
import os
import socket
import sys
import threading
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from pymavlink import mavutil
except ImportError:  # pragma: no cover
    mavutil = None


def free_udp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeVehicle(threading.Thread):
    """Heartbeat + ATTITUDE at 10 Hz; collects RC_CHANNELS_OVERRIDE."""

    def __init__(self, port):
        super().__init__(daemon=True)
        self.conn = mavutil.mavlink_connection(f"udpout:127.0.0.1:{port}", source_system=1, source_component=1)
        self.overrides = []
        self.running = True

    def run(self):
        last = 0
        while self.running:
            if time.time() - last > 0.1:
                self.conn.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_SUBMARINE, mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA,
                                             0, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
                self.conn.mav.attitude_send(int(time.time() * 1000) % 2**32, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
                last = time.time()
            msg = self.conn.recv_match(type="RC_CHANNELS_OVERRIDE", blocking=False)
            if msg:
                self.overrides.append((msg.chan1_raw, msg.chan2_raw, msg.chan3_raw, msg.chan4_raw,
                                       msg.chan5_raw, msg.chan6_raw))
            time.sleep(0.005)


@unittest.skipIf(mavutil is None, "pymavlink not installed")
class ArduSubBackendIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.port = free_udp_port()
        cfg = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
        cfg.read(os.path.join(ROOT, "QGC", "config.ini"), encoding="utf-8")
        cfg.set("Connection", "udp_host", "127.0.0.1")
        cfg.set("Connection", "udp_port", str(self.port))
        cfg.set("AutoControl", "enable_depth_hold", "false")
        cfg.set("AutoControl", "enable_heading_hold", "false")
        self.cfg_path = os.path.join(ROOT, "tests", f"_itest_{self.port}.ini")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            cfg.write(f)
        self.vehicle = FakeVehicle(self.port)
        self.vehicle.start()

    def tearDown(self):
        self.vehicle.running = False
        os.remove(self.cfg_path)

    def test_forward_drives_channel_5_then_returns_to_centre(self):
        from rov_backend import ArduSubBackend
        backend = ArduSubBackend(config_file=self.cfg_path)
        try:
            backend.execute("forward", "high")
            time.sleep(0.3)  # let the final zero frames arrive
        finally:
            backend.close()
        ov = self.vehicle.overrides
        self.assertTrue(ov, "vehicle received no RC_CHANNELS_OVERRIDE")
        ch5 = [o[4] for o in ov]
        self.assertGreater(max(ch5), 1500, "forward thrust never went positive on channel 5")
        self.assertEqual(ch5[-1], 1500, "channel 5 not centred after the action")
        for i in (0, 1, 2, 3, 5):  # pitch, roll, vertical, yaw, lateral stay centred
            self.assertEqual({o[i] for o in ov}, {1500}, f"channel {i + 1} moved")


if __name__ == "__main__":
    unittest.main()
