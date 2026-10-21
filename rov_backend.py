"""
ROV 执行后端抽象层。

小脑输出的是离散动作（方向 + 速度档位）。这个模块把"执行一个离散动作"
和"动作如何落到硬件上"分开：

    backend = make_backend("sim")        # 打印模拟（原 RovController 行为）
    backend = make_backend("ardusub")    # 走 QGC/ 下的 MAVLink + MPC 栈
    backend.execute("前", "medium")      # 阻塞直到这个动作执行完毕
    backend.stop()
    backend.close()

方向与速度使用小脑的原始枚举：方向 ['前','后','左','右','停']，
速度 ['low','medium','high','stop']。
"""
import os
import sys
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DIRECTIONS = ('前', '后', '左', '右', '停')
SPEEDS = ('low', 'medium', 'high', 'stop')

QGC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'QGC')


class RovBackend:
    """执行后端基类"""

    def execute(self, direction: str, speed: str) -> None:
        """执行一个离散动作，返回时动作已经结束（ROV 已停止或回到悬停）。"""
        raise NotImplementedError

    def stop(self) -> None:
        """立即停止。"""
        raise NotImplementedError

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def validate_action(direction: str, speed: str):
    if direction not in DIRECTIONS:
        raise ValueError(f"无效方向 {direction!r}，应为 {DIRECTIONS}")
    if speed not in SPEEDS:
        raise ValueError(f"无效速度 {speed!r}，应为 {SPEEDS}")


# ---------------------------------------------------------------------------
# 模拟后端：保留原项目的"5 秒先加速再减速"梯形曲线
# ---------------------------------------------------------------------------

SIM_DIRECTION_MAP = {'前': 'forward', '后': 'backward', '左': 'left', '右': 'right', '停': 'stop'}
SIM_SPEED_MAP = {'low': 100, 'medium': 200, 'high': 300, 'stop': 0}


class SimulatedBackend(RovBackend):
    """
    使用 QGC/rov_movement.RovMovement（默认内部是打印模拟的 RovController）。
    动作执行方式与原 dual_brain_core.MPCController 一致：total_time 秒内
    前半段线性加速到目标速度，后半段线性减速到 0。
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

        logger.info("模拟执行: 方向=%s 目标速度=%s", mapped_direction, target_speed)
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
# ArduSub 后端：MavlinkInterface + AutoController(MPC)，不依赖键盘/pygame
# ---------------------------------------------------------------------------

class ArduSubBackend(RovBackend):
    """
    通过 QGC/ 下的 MavlinkInterface 与 AutoController 驱动真实 ArduSub ROV。

    与 QGC/main_controller.ROVMainController 的区别：
      - 不创建 VirtualJoystick（不需要 keyboard/pygame，也不需要 root），可无头运行
      - 不注册 SIGINT 处理器，由调用方决定退出方式
      - execute() 是阻塞的：把动作交给 MPC 后一直等到 MPC 的控制时域结束

    每个离散动作由 MPC 以 control_horizon（默认 1 秒）的参考轨迹执行；
    repeats 控制同一个动作连续执行几个时域，默认 1。
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
            raise RuntimeError(f"MAVLink 连接失败（配置: {self.config_file}）")
        self.auto.start()
        self._running = True
        self._thread = threading.Thread(target=self._send_loop, daemon=True)
        self._thread.start()
        logger.info("ArduSubBackend 已启动")

    def _send_loop(self):
        """把 AutoController 的输出以固定频率发给 ROV（等价于 ROVMainController._auto_control_loop）"""
        while self._running:
            try:
                state = self.mavlink.get_vehicle_state()
                self.auto.update_vehicle_state(state)
                out = self.auto.get_control_outputs()
                # forward/lateral 只有在 AutoController 提供时才传（兼容新旧 QGC 栈）
                extra = {k: out[k] for k in ('forward', 'lateral') if k in out}
                self.mavlink.send_manual_control(
                    roll=out['roll'], pitch=out['pitch'],
                    throttle=out['throttle'], yaw=out['yaw'], **extra)
            except Exception as e:  # 不能让发送线程死掉
                logger.error("ArduSub 发送循环错误: %s", e)
            time.sleep(self.loop_period)

    def execute(self, direction: str, speed: str) -> None:
        validate_action(direction, speed)
        if direction == '停' or speed == 'stop':
            self.stop()
            return
        mpc = self.auto.mpc_controller
        for _ in range(self.repeats):
            self.auto.execute_vla_command(direction, speed)
            deadline = time.time() + mpc.control_horizon + self.timeout_margin
            while mpc.is_active and time.time() < deadline:
                time.sleep(0.02)
            if mpc.is_active:
                logger.warning("MPC 未在预期时间内结束，强制停止")
                self.stop()
                return

    def stop(self) -> None:
        self.auto.execute_vla_command('停', 'stop')
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
    "ardusub"  -> ArduSubBackend（kwargs: config_file, repeats）
    """
    spec = (spec or 'sim').strip().lower()
    if spec == 'sim':
        return SimulatedBackend(**kwargs)
    if spec == 'ardusub':
        return ArduSubBackend(**kwargs)
    raise ValueError(f"未知后端: {spec!r}")
