#!/usr/bin/env python3
"""
Offline replay: re-run the small brain over decision_log.json and the screenshots in FIG/ to compare prompts/models without putting the ROV in the water.

  python replay.py --instruction exp1            # re-query the small brain, report agreement / JSON validity / latency
  python replay.py --instruction exp1 --dry-run  # only summarise the decisions already in the log
  python replay.py --plan none                   # ablation: executor without the cloud plan
  python replay.py --plan fixed                  # ablation: a generic plan that says nothing task-specific
  python replay.py --history 0,3,5,10            # sweep how many prior actions the executor is shown
  python replay.py --calibration                 # is self-reported confidence predictive of agreement?
  python replay.py --blank-instruction           # ablation: no language, only images
  python replay.py --grey-frames                 # ablation: no vision, only language
  python replay.py --models qwen2.5-vl-7b-instruct,qwen2.5-vl-3b-instruct   # size vs agreement/latency

Each small-brain decision is paired with the two most recent screenshots before it (by filename timestamp).
"""
import argparse
import base64
import collections
import glob
import json
import os
import statistics
import sys
import time
from collections import Counter
from datetime import datetime

from rov_backend import LEGACY_DIRECTIONS

FIG_TS_FMT = "%Y-%m-%d_%H-%M-%S"

OPPOSITES = {("forward", "backward"), ("left", "right"), ("up", "down"), ("turn_left", "turn_right")}

# A plan with the right shape and no task content, to test whether the cloud brain's
# content matters or only the presence of a plan in the prompt.
FIXED_PLAN = {"reasoning": "Generic plan.",
              "task_plan": [{"step": 1, "description": "Look for the target and move toward it.",
                             "target_object": "target", "obstacle_to_avoid": "any obstacle", "confidence": 0.5},
                            {"step": 2, "description": "Stop when the target is reached.",
                             "target_object": "target", "obstacle_to_avoid": "any obstacle", "confidence": 0.5}],
              "total_steps": 2, "estimated_completion_time": "unknown"}


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
    cases, plan, step, prior = [], None, 1, []
    for ts, d in log:
        if not isinstance(d, dict):
            continue
        if "task_plan" in d:
            plan, step, prior = d, 1, []
            continue
        if "action" not in d:
            continue
        cases.append({"ts": ts, "decision": d, "plan": plan, "step": step,
                      "frames": frames_before(figs, ts), "prior": list(prior)})
        a = d["action"]
        prior.append({"direction": LEGACY_DIRECTIONS.get(a.get("direction"), a.get("direction")),
                      "speed": a.get("speed"), "step_completed": d.get("step_completed", True)})
        if d.get("step_completed", True):
            step += 1
    return cases


def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def grey_frame_b64(size=(64, 64)):
    """A flat grey image, same shape as a real frame, so the vision input carries no information."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", size, (128, 128, 128)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def plan_for(case, mode):
    """mode: 'logged' (what the cloud brain produced), 'none' (no plan), 'fixed' (FIXED_PLAN)."""
    return {"logged": case["plan"], "none": None, "fixed": FIXED_PLAN}[mode]


def replay(cases, instruction, brain, plan_mode="logged", history_len=None, grey_frames=False):
    """Re-query the small brain and return a result dict per case.

    history_len: if given, brain.history is filled with the last N logged actions before each case
    (what the executor would have seen live). None leaves brain.history untouched.
    grey_frames: replace both images with a flat grey frame (vision ablation).
    """
    results = []
    grey = grey_frame_b64() if grey_frames else None
    for c in cases:
        if len(c["frames"]) < 2:
            results.append({**c, "new": None, "latency": None, "skipped": "no frames"})
            continue
        if history_len is not None:
            brain.history = collections.deque(c["prior"][-history_len:] if history_len else [], maxlen=max(history_len, 1))
        imgs = [grey, grey] if grey else [b64(p) for p in c["frames"]]
        plan = plan_for(c, plan_mode)
        t0 = time.time()
        new = brain.call_lmstudio_api(imgs[0], instruction, plan, c["step"] if plan else None, imgs[1])
        results.append({**c, "new": new, "latency": time.time() - t0})
    return results


def logged_dir(r):
    """Logged direction, with pre-translation Chinese tokens normalised to English."""
    d = r["decision"]["action"].get("direction")
    return LEGACY_DIRECTIONS.get(d, d)


def oscillation_rate(directions):
    """Fraction of consecutive pairs that are opposite moves (forward then backward, ...)."""
    pairs = list(zip(directions, directions[1:]))
    if not pairs:
        return 0.0
    return sum(1 for a, b in pairs if (a, b) in OPPOSITES or (b, a) in OPPOSITES) / len(pairs)


CONF_BUCKETS = ((0.0, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01))


def calibration_table(results):
    """
    Per confidence bucket of the *new* answer: count and agreement rate with the logged action.

    Agreement with the log is a proxy for correctness, since the log carries no ground
    truth; a well-calibrated model should agree more often when it says it is confident.
    Returns (lines, pairs) where pairs is [(confidence, agreed)] for further analysis.
    """
    pairs = []
    for r in results:
        new = r.get("new")
        if not isinstance(new, dict) or "action" not in new:
            continue
        c = new["action"].get("confidence")
        if isinstance(c, (int, float)):
            pairs.append((float(c), new["action"].get("direction") == logged_dir(r)))
    lines = ["confidence  n  agreement"]
    for lo, hi in CONF_BUCKETS:
        b = [a for c, a in pairs if lo <= c < hi]
        lines.append(f"[{lo:.1f},{min(hi, 1.0):.1f}) {len(b):3d}  {sum(b) / len(b):.2f}" if b
                     else f"[{lo:.1f},{min(hi, 1.0):.1f})   0  -")
    if pairs:
        confs = [c for c, _ in pairs]
        lines.append(f"distinct confidence values: {len(set(confs))} (spread {min(confs):.2f}-{max(confs):.2f})")
    return lines, pairs


def model_row(results):
    """Compact per-model metrics for a comparison table."""
    ran = [r for r in results if not r.get("skipped")]
    valid = [r for r in ran if isinstance(r["new"], dict) and "action" in r["new"]]
    agree = [r for r in valid if r["new"]["action"].get("direction") == logged_dir(r)]
    lat = [r["latency"] for r in ran if r["latency"] is not None]
    return {"valid": len(valid) / len(ran) if ran else 0.0,
            "agree": len(agree) / len(valid) if valid else 0.0,
            "osc": oscillation_rate([r["new"]["action"].get("direction") for r in valid]),
            "done": completion_index(results),
            "lat_mean": statistics.mean(lat) if lat else 0.0,
            "lat_max": max(lat) if lat else 0.0}


def completion_index(results):
    """1-based index of the first replayed decision that reports status done, or None."""
    for i, r in enumerate(results, 1):
        if isinstance(r.get("new"), dict) and r["new"].get("status") == "done":
            return i
    return None


def summarize(results, dry_run):
    old_dirs = Counter(logged_dir(r) for r in results)
    confs = [r["decision"]["action"].get("confidence") for r in results
             if isinstance(r["decision"]["action"].get("confidence"), (int, float))]
    lines = [f"cases: {len(results)}",
             f"logged directions: {dict(old_dirs)}",
             f"logged mean confidence: {statistics.mean(confs):.2f}" if confs else "logged mean confidence: n/a"]
    if dry_run:
        return "\n".join(lines)
    ran = [r for r in results if not r.get("skipped")]
    valid = [r for r in ran if isinstance(r["new"], dict) and "action" in r["new"]]
    agree = [r for r in valid if r["new"]["action"].get("direction") == logged_dir(r)]
    lat = [r["latency"] for r in ran if r["latency"] is not None]
    new_dirs = [r["new"]["action"].get("direction") for r in valid]
    done_at = completion_index(results)
    lines += [f"replayed: {len(ran)} (skipped {len(results) - len(ran)} without frames)",
              f"valid JSON: {len(valid)}/{len(ran)}",
              f"direction agreement: {len(agree)}/{len(valid)}",
              f"new directions: {dict(Counter(new_dirs))}",
              f"oscillation rate: new {oscillation_rate(new_dirs):.2f} / logged "
              f"{oscillation_rate([logged_dir(r) for r in results]):.2f}",
              f"first 'done' at decision: {done_at if done_at else 'never'}",
              f"latency s: mean {statistics.mean(lat):.2f} max {max(lat):.2f}" if lat else "latency: n/a"]
    for r in valid:
        if r not in agree:
            lines.append(f"  mismatch @{r['ts']:.0f}: logged {logged_dir(r)} "
                         f"-> new {r['new']['action'].get('direction')}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline replay of small-brain decisions")
    p.add_argument("--log", default="decision_log.json")
    p.add_argument("--fig-dir", default="FIG")
    p.add_argument("--instruction", "-i", default="exp1", help="instruction or preset name (exp1/exp2/exp3)")
    p.add_argument("--dry-run", action="store_true", help="do not call the model, only summarise the log")
    p.add_argument("--plan", choices=["logged", "none", "fixed"], default="logged",
                   help="which task plan the executor sees: the logged cloud plan, none, or a generic fixed plan")
    p.add_argument("--blank-instruction", action="store_true", help="send an empty instruction (language ablation)")
    p.add_argument("--grey-frames", action="store_true", help="send flat grey images (vision ablation)")
    p.add_argument("--models", help="comma-separated LM Studio model names to compare on the same cases")
    p.add_argument("--calibration", action="store_true", help="print agreement rate per confidence bucket")
    p.add_argument("--history", help="comma-separated history lengths to sweep, e.g. 0,3,5,10 (default: model default)")
    p.add_argument("--out", help="write per-case results to a JSON file")
    a = p.parse_args(argv)

    cases = build_cases(load_log(a.log), load_figs(a.fig_dir))
    if a.dry_run:
        results = [{**c, "new": None, "latency": None} for c in cases]
    else:
        from dual_brain_core import SmallBrain
        from rov_backend import RovBackend

        class NoBackend(RovBackend):  # replay never moves anything
            def execute(self, direction, speed):
                pass

            def stop(self):
                pass

        brain = SmallBrain(backend=NoBackend(), decision_timeout=180.0)
        instruction = "" if a.blank_instruction else brain.preset_instructions.get(a.instruction, a.instruction)
        if a.models:
            rows = []
            for m in a.models.split(","):
                brain.LMSTUDIO_MODEL = m.strip()
                rs = replay(cases, instruction, brain, a.plan, grey_frames=a.grey_frames)
                rows.append((m.strip(), model_row(rs)))
            print(f"{'model':40s} valid  agree  osc   done  lat_mean  lat_max")
            for m, r in rows:
                print(f"{m:40s} {r['valid']:5.2f}  {r['agree']:5.2f}  {r['osc']:4.2f}  {str(r['done']):>4s}  "
                      f"{r['lat_mean']:8.2f}  {r['lat_max']:7.2f}")
            return 0
        if a.history:
            for n in (int(x) for x in a.history.split(",")):
                print(f"\n=== history length {n} ===")
                print(summarize(replay(cases, instruction, brain, a.plan, history_len=n, grey_frames=a.grey_frames), False))
            return 0
        results = replay(cases, instruction, brain, a.plan, grey_frames=a.grey_frames)
    print(summarize(results, a.dry_run))
    if a.calibration and not a.dry_run:
        print("\n".join(calibration_table(results)[0]))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
