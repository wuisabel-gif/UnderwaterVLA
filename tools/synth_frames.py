#!/usr/bin/env python3
"""
Generate SYNTHETIC frames for a decision log so replay.py has images to pair with each decision.

Draws a simple underwater tank scene (blue water, three vertical pillars, floor) and writes two
PNGs per decision, timestamped 6 s and 5 s before it, so `frames_before` picks them up. The
camera drifts toward the far pillar over the course of each task so consecutive frames differ.

These are NOT real camera images. Results produced from them validate the pipeline, not the
paper's claims. Output directory defaults to FIG_synthetic/ to keep that distinction visible.

  python tools/synth_frames.py --log decision_log.json --out FIG_synthetic
"""
import argparse
import json
import os
import sys
from datetime import datetime

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from replay import FIG_TS_FMT, load_log  # noqa: E402

W, H = 640, 480


def scene(progress, jitter=0.0):
    """progress 0..1: how far along the approach to the far pillar; jitter shifts the view slightly."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):  # water gradient, murkier lower down
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(20 + 40 * t), int(90 + 60 * t), int(140 + 40 * t)))
    d.rectangle([0, int(H * 0.8), W, H], fill=(70, 90, 80))  # tank floor
    # three pillars; the far one grows as we approach, the middle one is the obstacle
    for cx, base_w, depth in ((W * (0.25 + jitter), 40, 0.5), (W * (0.5 + jitter), 55, 0.7), (W * (0.78 + jitter), 30, 1.0)):
        scale = 1 + 1.5 * progress * depth
        w = base_w * scale
        top = H * (0.35 - 0.2 * progress * depth)
        d.rectangle([cx - w / 2, top, cx + w / 2, H * 0.8], fill=(200, 190, 160), outline=(120, 110, 90))
    return img


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="decision_log.json")
    p.add_argument("--out", default="FIG_synthetic")
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    decisions = [(ts, d) for ts, d in load_log(a.log) if isinstance(d, dict) and "action" in d]
    n = 0
    for i, (ts, _) in enumerate(decisions):
        progress = i / max(1, len(decisions) - 1)
        for k, dt in enumerate((6, 5)):
            name = datetime.fromtimestamp(ts - dt).strftime(FIG_TS_FMT) + f"_{k:03d}.png"
            scene(progress, jitter=0.01 * k).save(os.path.join(a.out, name))
            n += 1
    print(f"wrote {n} synthetic frames for {len(decisions)} decisions to {a.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
