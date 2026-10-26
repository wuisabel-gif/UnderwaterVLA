import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
import replay


def act(d, **extra):
    return {"action": {"direction": d, "speed": "low", "confidence": 0.9}, "status": "in_progress", **extra}


class FakeBrain:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def call_lmstudio_api(self, img1, instruction, plan, step, img2):
        self.calls.append((plan, step))
        return self.answers.pop(0)


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fig = os.path.join(self.tmp.name, "FIG")
        os.makedirs(self.fig)
        # frames at 10:00:00, 10:00:01, then a decision at 10:00:05, frames at :10 :11, decision at :15
        base = "2025-01-01_10-00-"
        for sec in ("00", "01", "10", "11"):
            Image.new("RGB", (2, 2)).save(os.path.join(self.fig, f"{base}{sec}.png"))
        from datetime import datetime
        t = lambda s: datetime.strptime(f"2025-01-01_10-00-{s}", replay.FIG_TS_FMT).timestamp()
        self.log = os.path.join(self.tmp.name, "log.json")
        with open(self.log, "w", encoding="utf-8") as f:
            f.write(json.dumps({"timestamp": t("03"), "decision": {"task_plan": [1], "total_steps": 1}}) + "\n")
            f.write("not json\n")
            f.write(json.dumps({"timestamp": t("05"), "decision": act("forward", step_completed=False)}) + "\n")
            f.write(json.dumps({"timestamp": t("15"), "decision": act("right")}) + "\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_cases_pair_frames_and_carry_plan(self):
        cases = replay.build_cases(replay.load_log(self.log), replay.load_figs(self.fig))
        self.assertEqual(len(cases), 2)
        self.assertTrue(cases[0]["frames"][0].endswith("00.png") and cases[0]["frames"][1].endswith("01.png"))
        self.assertTrue(cases[1]["frames"][1].endswith("11.png"))
        self.assertEqual(cases[0]["plan"]["total_steps"], 1)
        self.assertEqual((cases[0]["step"], cases[1]["step"]), (1, 1))  # step 1 not completed -> stays 1

    def test_replay_summary(self):
        cases = replay.build_cases(replay.load_log(self.log), replay.load_figs(self.fig))
        brain = FakeBrain([act("forward"), None])
        out = replay.summarize(replay.replay(cases, "go", brain), dry_run=False)
        self.assertIn("valid JSON: 1/2", out)
        self.assertIn("direction agreement: 1/1", out)
        self.assertEqual(len(brain.calls), 2)

    def test_plan_modes(self):
        cases = replay.build_cases(replay.load_log(self.log), replay.load_figs(self.fig))
        for mode, expect in (("logged", cases[0]["plan"]), ("none", None), ("fixed", replay.FIXED_PLAN)):
            brain = FakeBrain([act("forward"), act("forward")])
            replay.replay(cases, "go", brain, plan_mode=mode)
            self.assertEqual(brain.calls[0][0], expect, mode)
            self.assertEqual(brain.calls[0][1], None if expect is None else 1)

    def test_oscillation_and_completion(self):
        self.assertEqual(replay.oscillation_rate(["forward", "backward", "forward", "left"]), 2 / 3)
        self.assertEqual(replay.oscillation_rate(["forward"]), 0.0)
        results = [{"new": act("forward")}, {"new": None}, {"new": {**act("stop"), "status": "done"}}]
        self.assertEqual(replay.completion_index(results), 3)
        self.assertIsNone(replay.completion_index(results[:2]))

    def test_history_sweep_feeds_prior_actions(self):
        cases = replay.build_cases(replay.load_log(self.log), replay.load_figs(self.fig))
        self.assertEqual(cases[0]["prior"], [])
        self.assertEqual([p["direction"] for p in cases[1]["prior"]], ["forward"])

        class HistBrain(FakeBrain):
            def call_lmstudio_api(self, *a):
                self.calls.append(list(self.history))
                return self.answers.pop(0)

        brain = HistBrain([act("forward"), act("right")])
        replay.replay(cases, "go", brain, history_len=5)
        self.assertEqual(brain.calls, [[], [{"direction": "forward", "speed": "low", "step_completed": False}]])
        brain = HistBrain([act("forward"), act("right")])
        replay.replay(cases, "go", brain, history_len=0)
        self.assertEqual(brain.calls, [[], []])

    def test_dry_run_counts(self):
        out = replay.main(["--log", self.log, "--fig-dir", self.fig, "--dry-run"])
        self.assertEqual(out, 0)


if __name__ == "__main__":
    unittest.main()
