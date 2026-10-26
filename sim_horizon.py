#!/usr/bin/env python3
"""
Toy 1-D simulation to study the MPC action horizon (research question 5).

The vehicle is a point mass with quadratic drag using the [MPC] parameters from
QGC/config.ini. A scripted executor stands in for the VLM: it picks a speed level from the
remaining distance, pays a decision latency during which the vehicle coasts, then the real
MPCController profile/controller from QGC/ drives the thruster for one horizon. Sweeps the
horizon and the latency and prints decisions, time and final error per combination.

  python sim_horizon.py
  python sim_horizon.py --horizons 0.5,1,2,3 --latencies 0,2,5 --goal 5
"""
import argparse
import configparser
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "QGC"))
from auto_controller import MPCController  # noqa: E402

F_MAX = 5.0  # N at full command. ponytail: ~1 m/s terminal speed with drag 5; calibrate on the real vehicle
TOL = 0.3    # m, "arrived"


def scripted_executor(distance):
    """Stand-in for the VLM: speed level from remaining distance."""
    if abs(distance) < TOL:
        return "stop"
    if abs(distance) > 3:
        return "high"
    if abs(distance) > 1:
        return "medium"
    return "low"


def run(horizon, latency, goal, config, max_decisions=200, dt=0.02):
    mpc = MPCController(config)
    mpc.control_horizon = horizon
    mpc.steps = int(horizon / mpc.control_interval)
    x = v = t = 0.0
    max_x = 0.0

    def integrate(u, seconds):
        nonlocal x, v, t, max_x
        for _ in range(int(seconds / dt)):
            drag = config.getfloat("MPC", "translational_drag_coeff", fallback=5.0) * v * abs(v)
            v += (u * F_MAX - drag) / mpc.mass * dt
            x += v * dt
            t += dt
            max_x = max(max_x, x)

    for n in range(1, max_decisions + 1):
        level = scripted_executor(goal - x)
        integrate(0.0, latency)                       # thinking: coast
        if level == "stop":
            return {"decisions": n, "time": t, "error": goal - x, "overshoot": max(0.0, max_x - goal)}
        mpc.set_vla_command("forward" if goal > x else "backward", level)
        for ref in mpc.reference_profile:             # one horizon, open the MPC loop by hand
            mpc.current_velocity = v
            mpc._estimate_drag()
            integrate(mpc._compute_translational_control(ref), dt)
        integrate(0.0, 0.0)
    return {"decisions": n, "time": t, "error": goal - x, "overshoot": max(0.0, max_x - goal)}


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--horizons", default="0.5,1,2,3")
    p.add_argument("--latencies", default="0,2,5", help="seconds the executor takes per decision")
    p.add_argument("--goal", type=float, default=5.0, help="metres to travel")
    p.add_argument("--config", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "QGC", "config.ini"))
    a = p.parse_args(argv)
    config = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
    config.read(a.config, encoding="utf-8")
    print(f"{'horizon':>7s} {'latency':>7s} {'decisions':>9s} {'time_s':>7s} {'final_err_m':>11s} {'overshoot_m':>11s}")
    for h in (float(x) for x in a.horizons.split(",")):
        for lat in (float(x) for x in a.latencies.split(",")):
            r = run(h, lat, a.goal, config)
            print(f"{h:7.2f} {lat:7.1f} {r['decisions']:9d} {r['time']:7.1f} {r['error']:11.2f} {r['overshoot']:11.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
