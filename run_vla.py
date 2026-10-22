#!/usr/bin/env python3
"""
Command-line entry point: wires the dual-brain VLA loop to an image source and an ROV backend.

Examples:
  # Original behaviour: screen capture + print-only simulation
  python run_vla.py --instruction exp1

  # USB camera + print-only simulation (verify the picture on the bench first)
  python run_vla.py --source camera:0 --instruction "Swim through the hula hoop"

  # BlueROV video stream + real ArduSub (MAVLink settings from QGC/config.ini)
  python run_vla.py --source udp://192.168.2.1:5600 --backend ardusub --instruction exp2

  # Omit --instruction for interactive mode
"""
import argparse
import logging
import sys

from dual_brain_oop import DualBrainController
from rov_backend import make_backend


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Dual-brain underwater VLA controller")
    p.add_argument("--source", default="screen",
                   help='image source: "screen", "camera:<index|path>", udp://, rtsp:// (default screen)')
    p.add_argument("--rotate", type=int, default=None,
                   help="rotation applied to captured frames (degrees, counter-clockwise positive). screen defaults to -90, camera to 0")
    p.add_argument("--backend", choices=["sim", "ardusub"], default="sim", help="execution backend (default sim)")
    p.add_argument("--config", default=None, help="config.ini path for the ardusub backend (default QGC/config.ini)")
    p.add_argument("--repeats", type=int, default=1, help="ardusub backend: how many consecutive MPC horizons each action runs")
    p.add_argument("--settle", type=float, default=2.0, help="seconds to wait after each action before capturing")
    p.add_argument("--max-steps", type=int, default=50, help="max actions per task")
    p.add_argument("--no-planner", action="store_true", help="skip cloud big-brain planning, use only the small brain")
    p.add_argument("--interactive", action="store_true", help="confirm each action with Enter")
    p.add_argument("--min-confidence", type=float, default=0.5, help="actions below this confidence become stop")
    p.add_argument("--decision-timeout", type=float, default=30.0, help="timeout in seconds for one small-brain call; stop on timeout")
    p.add_argument("--instruction", "-i", default=None,
                   help="task instruction or preset name (exp1/exp2/exp3). Omit for interactive mode")
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
        print(f"Instruction: {instruction}")
        done = controller.run_task(instruction)
        print("Task complete" if done else "Task not complete")
        return 0 if done else 1
    except KeyboardInterrupt:
        print("\nInterrupted by user, stopping ROV")
        backend.stop()
        return 130
    finally:
        controller.close()


if __name__ == "__main__":
    sys.exit(main())
