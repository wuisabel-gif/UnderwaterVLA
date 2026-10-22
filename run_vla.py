#!/usr/bin/env python3
"""
命令行入口：把双脑 VLA 循环接到指定的图像来源和 ROV 后端。

示例：
  # 旧行为：屏幕截图 + 打印模拟
  python run_vla.py --instruction exp1

  # USB 相机 + 打印模拟（先在岸上验证画面）
  python run_vla.py --source camera:0 --instruction "钻过呼啦圈"

  # BlueROV 视频流 + 真实 ArduSub（通过 QGC/config.ini 的 MAVLink 设置）
  python run_vla.py --source udp://192.168.2.1:5600 --backend ardusub --instruction exp2

  # 不传 --instruction 则进入交互模式
"""
import argparse
import logging
import sys

from dual_brain_oop import DualBrainController
from rov_backend import make_backend


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dual-brain underwater VLA controller")
    p.add_argument("--source", default="screen",
                   help='图像来源: "screen"、"camera:<index|path>"、udp://、rtsp:// (默认 screen)')
    p.add_argument("--rotate", type=int, default=None,
                   help="抓到的图像旋转角度（度，逆时针为正）。screen 默认 -90，camera 默认 0")
    p.add_argument("--backend", choices=["sim", "ardusub"], default="sim", help="执行后端 (默认 sim)")
    p.add_argument("--config", default=None, help="ardusub 后端使用的 config.ini 路径 (默认 QGC/config.ini)")
    p.add_argument("--repeats", type=int, default=1, help="ardusub 后端每个动作连续执行几个 MPC 时域")
    p.add_argument("--settle", type=float, default=2.0, help="动作结束后等待多少秒再抓图")
    p.add_argument("--max-steps", type=int, default=50, help="单个任务最多动作数")
    p.add_argument("--no-planner", action="store_true", help="跳过云端大脑规划，仅用小脑")
    p.add_argument("--interactive", action="store_true", help="每个动作后按回车确认")
    p.add_argument("--min-confidence", type=float, default=0.5, help="低于此置信度的动作改为停止")
    p.add_argument("--decision-timeout", type=float, default=30.0, help="小脑单次调用超时秒数，超时则停止")
    p.add_argument("--instruction", "-i", default=None,
                   help="任务指令或预设名 (exp1/exp2/exp3)。不传则进入交互模式")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    from image_source import make_image_source
    src_kwargs = {}
    if args.rotate is not None:
        src_kwargs["rotate"] = args.rotate
    image_source = make_image_source(args.source, **src_kwargs)

    backend_kwargs = {}
    if args.backend == "ardusub":
        backend_kwargs = {"config_file": args.config, "repeats": args.repeats}
    backend = make_backend(args.backend, **backend_kwargs)

    controller = DualBrainController(
        backend=backend,
        image_source=image_source,
        settle_time=args.settle,
        interactive=args.interactive,
        min_confidence=args.min_confidence,
        decision_timeout=args.decision_timeout,
        max_steps=args.max_steps,
        use_planner=not args.no_planner,
    )

    try:
        if args.instruction is None:
            controller.run()
            return 0
        instruction = controller.big_brain.preset_instructions.get(args.instruction, args.instruction)
        print(f"指令: {instruction}")
        done = controller.run_task(instruction)
        print("任务完成" if done else "任务未完成")
        return 0 if done else 1
    except KeyboardInterrupt:
        print("\n用户中断，停止 ROV")
        backend.stop()
        return 130
    finally:
        controller.close()


if __name__ == "__main__":
    sys.exit(main())
