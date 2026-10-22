#!/usr/bin/env python3
"""
Offline replay: re-run the small brain over decision_log.json and the screenshots in FIG/ to compare prompts/models without putting the ROV in the water.

  python replay.py --instruction exp1            # re-query the small brain, report agreement / JSON validity / latency
  python replay.py --instruction exp1 --dry-run  # only summarise the decisions already in the log

Each small-brain decision is paired with the two most recent screenshots before it (by filename timestamp).
"""
import argparse
import base64
import glob
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime

FIG_TS_FMT = "%Y-%m-%d_%H-%M-%S"


def load_log(path):
    """Return [(timestamp, decision)] sorted by time. Bad lines are skipped."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
                out.append((float(e["timestamp"]), e["decision"]))
            except (ValueError, KeyError, TypeError):
                continue
    return sorted(out, key=lambda x: x[0])


def load_figs(fig_dir):
    """Return [(timestamp, path)] sorted by time; the first 19 characters of the filename are the timestamp."""
    out = []
    for p in glob.glob(os.path.join(fig_dir, "*.png")):
        try:
            ts = datetime.strptime(os.path.basename(p)[:19], FIG_TS_FMT).timestamp()
            out.append((ts, p))
        except ValueError:
            continue
    return sorted(out)


def frames_before(figs, ts, n=2):
    """The last n screenshots with timestamp <= ts, in time order."""
    before = [p for t, p in figs if t <= ts]
    return before[-n:]


def build_cases(log, figs):
    """Turn the log into replay cases: each small-brain decision + the task plan/step at the time + two frames."""
    cases, plan, step = [], None, 1
    for ts, d in log:
        if not isinstance(d, dict):
            continue
        if "task_plan" in d:
            plan, step = d, 1
            continue
        if "action" not in d:
            continue
        cases.append({"ts": ts, "decision": d, "plan": plan, "step": step,
                      "frames": frames_before(figs, ts)})
        if d.get("step_completed", True):
            step += 1
    return cases


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def replay(cases, instruction, brain):
    """Re-query the small brain and return a result dict per case."""
    results = []
    for c in cases:
        if len(c["frames"]) < 2:
            results.append({**c, "new": None, "latency": None, "skipped": "no frames"})
            continue
        imgs = [b64(p) for p in c["frames"]]
        t0 = time.time()
        new = brain.call_lmstudio_api(imgs[0], instruction, c["plan"], c["step"], imgs[1])
        results.append({**c, "new": new, "latency": time.time() - t0})
    return results


def summarize(results, dry_run):
    old_dirs = Counter(r["decision"]["action"].get("direction") for r in results)
    confs = [r["decision"]["action"].get("confidence") for r in results
             if isinstance(r["decision"]["action"].get("confidence"), (int, float))]
    lines = [f"cases: {len(results)}",
             f"logged directions: {dict(old_dirs)}",
             f"logged mean confidence: {statistics.mean(confs):.2f}" if confs else "logged mean confidence: n/a"]
    if dry_run:
        return "\n".join(lines)
    ran = [r for r in results if not r.get("skipped")]
    valid = [r for r in ran if isinstance(r["new"], dict) and "action" in r["new"]]
    agree = [r for r in valid if r["new"]["action"].get("direction") == r["decision"]["action"].get("direction")]
    lat = [r["latency"] for r in ran if r["latency"] is not None]
    lines += [f"replayed: {len(ran)} (skipped {len(results) - len(ran)} without frames)",
              f"valid JSON: {len(valid)}/{len(ran)}",
              f"direction agreement: {len(agree)}/{len(valid)}",
              f"latency s: mean {statistics.mean(lat):.2f} max {max(lat):.2f}" if lat else "latency: n/a"]
    for r in valid:
        if r not in agree:
            lines.append(f"  mismatch @{r['ts']:.0f}: logged {r['decision']['action'].get('direction')} "
                         f"-> new {r['new']['action'].get('direction')}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline replay of small-brain decisions")
    p.add_argument("--log", default="decision_log.json")
    p.add_argument("--fig-dir", default="FIG")
    p.add_argument("--instruction", "-i", default="exp1", help="instruction or preset name (exp1/exp2/exp3)")
    p.add_argument("--dry-run", action="store_true", help="do not call the model, only summarise the log")
    p.add_argument("--out", help="write per-case results to a JSON file")
    a = p.parse_args(argv)

    cases = build_cases(load_log(a.log), load_figs(a.fig_dir))
    if a.dry_run:
        results = [{**c, "new": None, "latency": None} for c in cases]
    else:
        from dual_brain_core import BaseBrain, SmallBrain
        brain = SmallBrain.__new__(SmallBrain)
        BaseBrain.__init__(brain)  # ponytail: skip SmallBrain.__init__, replay needs no ROV backend
        instruction = brain.preset_instructions.get(a.instruction, a.instruction)
        results = replay(cases, instruction, brain)
    print(summarize(results, a.dry_run))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
