"""
ROV execution backend abstraction.

The small brain outputs discrete actions (direction + speed level). This module separates
"execute one discrete action" from "how the action reaches the hardware":

    backend = make_backend("sim")        # print-only simulation (original RovController behaviour)
    backend = make_backend("ardusub")    # MAVLink + MPC stack under QGC/
    backend.execute("forward", "medium") # blocks until the action has finished
    backend.stop()
    backend.close()

Direction and speed use the small brain's raw enums: directions
['forward','backward','left','right','up','down','turn_left','turn_right','stop']
(left/right strafe, turn_left/turn_right yaw in place), speeds ['low','medium','high','stop'].
"""
import os
import sys
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DIRECTIONS = ('forward', 'backward', 'left', 'right', 'up', 'down', 'turn_left', 'turn_right', 'stop')
SPEEDS = ('low', 'medium', 'high', 'stop')

# Old Chinese tokens (pre-translation decision logs, or a model that slips into Chinese) -> English.
LEGACY_DIRECTIONS = {'前': 'forward', '后': 'backward', '左': 'left', '右': 'right', '上': 'up', '下': 'down',
                     '左转': 'turn_left', '右转': 'turn_right', '停': 'stop'}
LEGACY_STATUS = {'任务中': 'in_progress', '任务完成': 'done'}

QGC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'QGC')


class RovBackend:
    """Execution backend base class"""

    def execute(self, direction: str, speed: str) -> None:
        """Execute one discrete action; when this returns the action has ended (ROV stopped or back to hover)."""
        raise NotImplementedError

    def stop(self) -> None:
        """Stop immediately."""
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def validate_action(direction: str, speed: str):
    if direction not in DIRECTIONS:
        raise ValueError(f"Invalid direction {direction!r}, expected one of {DIRECTIONS}")
    if speed not in SPEEDS:
        raise ValueError(f"Invalid speed {speed!r}, expected one of {SPEEDS}")


# ---------------------------------------------------------------------------
# Simulated backend: keeps the original "5 s accelerate then decelerate" trapezoid profile
# ---------------------------------------------------------------------------

SIM_DIRECTION_MAP = {'forward': 'forward', 'backward': 'backward', 'left': 'left', 'right': 'right', 'up': 'up',
                     'down': 'down', 'turn_left': 'turn_left', 'turn_right': 'turn_right', 'stop': 'stop'}
SIM_SPEED_MAP = {'low': 100, 'medium': 200, 'high': 300, 'stop': 0}


class SimulatedBackend(RovBackend):
    """
    Uses QGC/rov_movement.RovMovement (by default a print-only RovController inside).
    Actions run the same way as the original dual_brain_core.MPCController: over total_time
    seconds, ramp linearly up to the target speed in the first half, then linearly down to 0.
    """

    def __init__(self, rov=None, total_time: float = 5.0, control_frequency: float = 1.0,
                 sleep=time.sleep):
        if rov is None:
            if QGC_DIR not in sys.path:
                sys.path.insert(0, QGC_DIR)
            from rov_movement import RovMovement
            rov = RovMovement()
        self.rov = rov
        self.total_time = total_time
        self.control_frequency = control_frequency
        self._sleep = sleep

    def execute(self, direction: str, speed: str) -> None:
        validate_action(direction, speed)
        mapped_direction = SIM_DIRECTION_MAP[direction]
        target_speed = SIM_SPEED_MAP[speed]
        if mapped_direction == 'stop' or target_speed == 0:
            self.stop()
            return

        time_step = 1.0 / self.control_frequency
        half = self.total_time / 2
        steps = max(1, int(half * self.control_frequency))
        speed_step = target_speed / steps

        logger.info("Simulated execution: direction=%s target speed=%s", mapped_direction, target_speed)
        for i in range(steps):
            self.rov.move(mapped_direction, int((i + 1) * speed_step), time_step)
            self._sleep(time_step)
        for i in range(steps):
            self.rov.move(mapped_direction, max(0, int(target_speed - (i + 1) * speed_step)), time_step)
            self._sleep(time_step)
        self.rov.move(mapped_direction, 0, time_step)

    def stop(self) -> None:
        self.rov.stop()

    def close(self) -> None:
        close = getattr(self.rov, 'close', None)
        if close:
            close()


# ---------------------------------------------------------------------------
# ArduSub backend: MavlinkInterface + AutoController(MPC), no keyboard/pygame dependency
# ---------------------------------------------------------------------------

class ArduSubBackend(RovBackend):
    """
    Drives a real ArduSub ROV through MavlinkInterface and AutoController from QGC/.

    Differences from QGC/main_controller.ROVMainController:
      - No VirtualJoystick (no keyboard/pygame, no root), so it runs headless
      - No SIGINT handler; the caller decides how to exit
      - execute() blocks: after handing the action to the MPC it waits for the MPC's control horizon to end

    Each discrete action is executed by the MPC as a reference trajectory of control_horizon
    (default 1 s); repeats sets how many consecutive horizons the same action runs, default 1.
    """

    def __init__(self, config_file: Optional[str] = None, repeats: int = 1,
                 loop_hz: float = 50.0, timeout_margin: float = 1.0):
        if QGC_DIR not in sys.path:
            sys.path.insert(0, QGC_DIR)
        from mavlink_interface import MavlinkInterface
        from auto_controller import AutoController
        import threading

        self.config_file = config_file or os.path.join(QGC_DIR, 'config.ini')
        self.repeats = max(1, int(repeats))
        self.loop_period = 1.0 / loop_hz
        self.timeout_margin = timeout_margin

        self.mavlink = MavlinkInterface(self.config_file)
        self.auto = AutoController(self.config_file)
        self._threading = threading
        self._running = False
        self._thread = None

        if not self.mavlink.connect():
            raise RuntimeError(f"MAVLink connection failed (config: {self.config_file})")
        self.auto.start()
        self._running = True
        self._thread = threading.Thread(target=self._send_loop, daemon=True)
        self._thread.start()
        logger.info("ArduSubBackend started")

    def _send_loop(self):
        """Send AutoController's outputs to the ROV at a fixed rate (equivalent to ROVMainController._auto_control_loop)"""
        while self._running:
            try:
                state = self.mavlink.get_vehicle_state()
                self.auto.update_vehicle_state(state)
                out = self.auto.get_control_outputs()
                # forward/lateral are only passed when AutoController provides them (old and new QGC stacks)
                extra = {k: out[k] for k in ('forward', 'lateral') if k in out}
                self.mavlink.send_manual_control(
                    roll=out['roll'], pitch=out['pitch'],
                    throttle=out['throttle'], yaw=out['yaw'], **extra)
            except Exception as e:  # the send thread must never die
                logger.error("ArduSub send loop error: %s", e)
            time.sleep(self.loop_period)

    def execute(self, direction: str, speed: str) -> None:
        validate_action(direction, speed)
        if direction == 'stop' or speed == 'stop':
            self.stop()
            return
        mpc = self.auto.mpc_controller
        for _ in range(self.repeats):
            self.auto.execute_vla_command(direction, speed)
            deadline = time.time() + mpc.control_horizon + self.timeout_margin
            while mpc.is_active and time.time() < deadline:
                time.sleep(0.02)
            if mpc.is_active:
                logger.warning("MPC did not finish within the expected time, forcing stop")
                self.stop()
                return

    def stop(self) -> None:
        self.auto.execute_vla_command('stop', 'stop')
        self.auto.mpc_controller.is_active = False

    def close(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
        try:
            self.auto.stop()
        finally:
            if self.mavlink.is_connected:
                self.mavlink.send_manual_control(0, 0, 0, 0)
                self.mavlink.disconnect()


def make_backend(spec: str = 'sim', **kwargs) -> RovBackend:
    """
    "sim"      -> SimulatedBackend
    "ardusub"  -> ArduSubBackend (kwargs: config_file, repeats)
    """
    spec = (spec or 'sim').strip().lower()
    if spec == 'sim':
        return SimulatedBackend(**kwargs)
    if spec == 'ardusub':
        return ArduSubBackend(**kwargs)
    raise ValueError(f"Unknown backend: {spec!r}")
