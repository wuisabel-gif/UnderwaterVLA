# Replay experiments on SYNTHETIC frames, 2026-10-26

**Read this first.** These numbers come from drawn tank scenes (`tools/synth_frames.py`, 320×240),
not camera images, paired with the 11 decisions in the September 2025 `decision_log.json`. The
executor was `qwen2.5vl:3b` (Q4_K_M) via Ollama on an 8 GB Apple M3, not the paper's 7B. They
validate that the pipeline and metrics work end to end and show which effects are large enough
to be worth measuring properly. They are not evidence about the paper's claims. n = 11.

"Agreement" is agreement with the logged action, which was itself produced by a 7B model on real
frames; it is a proxy, not ground truth.

## Summary table

| run | valid JSON | agree | oscillation | first `done` | latency s (mean) |
|---|---|---|---|---|---|
| RQ1 plan = logged | 11/11 | 3/11 | 0.10 | 6 | 52.2 (includes model load) |
| RQ1 plan = none | 11/11 | 2/11 | **0.60** | never | 5.7 |
| RQ2 plan = fixed generic | 10/11 | **5/10** | 0.00 | 11 | 5.9 |
| RQ3 history 0 | 11/11 | 2/11 | 0.20 | 6 | 8.0 |
| RQ3 history 3 | 11/11 | 3/11 | 0.00 | 6 | 7.8 |
| RQ3 history 5 | 11/11 | 3/11 | 0.00 | never | 7.5 |
| RQ3 history 10 | 10/11 | 2/10 | 0.22 | never | 9.8 |
| RQ6 blank instruction (plan kept) | 10/11 | 4/10 | 0.00 | 7 | 9.3 |
| RQ6 grey frames | 11/11 | 2/11 | 0.20 | never | 7.7 |
| RQ7 qwen2.5vl:3b (M3 laptop) | 11/11 | 2/11 | 0.20 | 6 | 11.2 |
| RQ7 qwen2.5vl:7b (RTX 4090, warm) | 11/11 | 4/11 | 0.20 | 7 | 0.9 |
| RQ7 qwen2.5vl:3b (RTX 4090, warm) | 11/11 | 2/11 | 0.20 | 10 | 0.4 |

Logged sequence oscillation rate for reference: 0.10.

## What stands out (synthetic, n = 11)

1. **No plan → the executor oscillates** (0.60 vs 0.10) and never declares completion. Having a
   plan in the prompt is the single largest effect seen.
2. **A generic plan with no task content did at least as well as the real cloud plan** (agreement
   5/10 vs 3/11, oscillation 0 vs 0.10). On this data the *presence* of a plan matters, its
   content does not. This is the cheapest claim in the paper to test for real.
3. **Short history helps, long history hurts.** 3–5 prior actions removed oscillation; 10 brought
   it back (0.22) and produced one invalid answer (the model drifted into Chinese).
4. **Confidence is not usable as a gate.** The model omitted the field in 4 of 11 answers and
   otherwise reported only 0.8–1.0; agreement was 0.20 in the ≥0.9 bucket and 0.00 in 0.7–0.9.
   With the current gate (missing → stop) 36% of steps would have been halted.
5. **Removing vision hurt more than removing the instruction**, but the language ablation is
   confounded: the logged plan was still in the prompt and names the pillar task. Re-run with
   `--plan none --blank-instruction` for a clean language ablation.
6. **7B vs 3B (added 2026-10-27, RTX 4090 in a dedicated container):** both 100% valid JSON; the
   7B agrees with the log a little more often (0.27–0.36 vs 0.09–0.18) at ~2× the latency (0.9 s vs
   0.4 s per call). Run-to-run variation at temperature 0.5 is as large as the gap, so n = 11 does
   not separate them. The 7B always emitted a confidence field (the 3B omitted it 4/11 times) but
   it is still uncalibrated: 0.22 agreement in the ≥0.9 bucket vs 0.50 in 0.7–0.9. The same 7B
   call took 352 s on the 8 GB laptop vs 0.9 s on the 4090.
7. Twice the model answered in Chinese despite an English prompt; the legacy token
   normalisation in `rov_backend.py` caught the actions.

## Reproduce

```bash
ollama pull qwen2.5vl:3b
export LMSTUDIO_API_URL=http://127.0.0.1:11434/v1 LMSTUDIO_API_KEY=ollama LMSTUDIO_MODEL=qwen2.5vl:3b
python3 tools/synth_frames.py --size 320x240
python3 replay.py --fig-dir FIG_synthetic -i exp1 --plan logged --calibration
python3 replay.py --fig-dir FIG_synthetic -i exp1 --plan none
python3 replay.py --fig-dir FIG_synthetic -i exp1 --plan fixed
python3 replay.py --fig-dir FIG_synthetic -i exp1 --history 0,3,5,10
python3 replay.py --fig-dir FIG_synthetic -i exp1 --blank-instruction
python3 replay.py --fig-dir FIG_synthetic -i exp1 --grey-frames
python3 replay.py --fig-dir FIG_synthetic -i exp1 --models qwen2.5vl:3b
```

## Raw output

### rq1_plan_logged
```
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 3/11
new directions: {'right': 3, 'forward': 2, 'turn_left': 3, 'stop': 1, 'left': 2}
oscillation rate: new 0.10 / logged 0.10
first 'done' at decision: 6
latency s: mean 52.15 max 64.17
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new turn_left
  mismatch @1757598192: logged stop -> new right
  mismatch @1757600433: logged forward -> new stop
  mismatch @1757600474: logged forward -> new right
  mismatch @1757600526: logged forward -> new left
  mismatch @1757600585: logged forward -> new turn_left
  mismatch @1757600683: logged forward -> new left
confidence  n  agreement
[0.0,0.5)   0  -
[0.5,0.7)   0  -
[0.7,0.9)   2  0.00
[0.9,1.0)   5  0.20
distinct confidence values: 4 (spread 0.80-1.00)
```
### rq1_plan_none
```
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 2/11
new directions: {'forward': 3, 'left': 4, 'right': 4}
oscillation rate: new 0.60 / logged 0.10
first 'done' at decision: never
latency s: mean 5.74 max 7.96
  mismatch @1757597485: logged right -> new forward
  mismatch @1757597708: logged right -> new forward
  mismatch @1757598192: logged stop -> new right
  mismatch @1757600433: logged forward -> new left
  mismatch @1757600474: logged forward -> new right
  mismatch @1757600526: logged forward -> new left
  mismatch @1757600585: logged forward -> new right
  mismatch @1757600639: logged forward -> new right
  mismatch @1757600683: logged forward -> new left
```
### rq2_plan_fixed
```
as it is the furthest one from my current position.",
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 10/11
direction agreement: 5/10
new directions: {'forward': 7, 'right': 1, 'left': 1, 'stop': 1}
oscillation rate: new 0.00 / logged 0.10
first 'done' at decision: 11
latency s: mean 5.86 max 8.79
  mismatch @1757597485: logged right -> new forward
  mismatch @1757597792: logged left -> new right
  mismatch @1757598192: logged stop -> new forward
  mismatch @1757600639: logged forward -> new left
  mismatch @1757600683: logged forward -> new stop
```
### rq3_history
```

=== history length 0 ===
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 2/11
new directions: {'right': 2, 'forward': 1, 'turn_left': 3, 'stop': 2, 'left': 3}
oscillation rate: new 0.20 / logged 0.10
first 'done' at decision: 6
latency s: mean 7.97 max 11.33
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new turn_left
  mismatch @1757598192: logged stop -> new turn_left
  mismatch @1757600433: logged forward -> new stop
  mismatch @1757600474: logged forward -> new stop
  mismatch @1757600526: logged forward -> new left
  mismatch @1757600585: logged forward -> new right
  mismatch @1757600639: logged forward -> new left
  mismatch @1757600683: logged forward -> new left

=== history length 3 ===
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 3/11
new directions: {'right': 2, 'forward': 4, 'stop': 1, 'left': 3, 'turn_right': 1}
oscillation rate: new 0.00 / logged 0.10
first 'done' at decision: 6
latency s: mean 7.82 max 9.57
  mismatch @1757597708: logged right -> new forward
  mismatch @1757597792: logged left -> new right
  mismatch @1757598192: logged stop -> new forward
  mismatch @1757600433: logged forward -> new stop
  mismatch @1757600474: logged forward -> new left
  mismatch @1757600526: logged forward -> new turn_right
  mismatch @1757600585: logged forward -> new left
  mismatch @1757600639: logged forward -> new left

=== history length 5 ===
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 3/11
new directions: {'right': 2, 'forward': 3, 'turn_left': 3, 'left': 3}
oscillation rate: new 0.00 / logged 0.10
first 'done' at decision: never
latency s: mean 7.48 max 9.83
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new right
  mismatch @1757598192: logged stop -> new forward
  mismatch @1757600433: logged forward -> new left
  mismatch @1757600474: logged forward -> new turn_left
  mismatch @1757600526: logged forward -> new left
  mismatch @1757600639: logged forward -> new turn_left
  mismatch @1757600683: logged forward -> new left

=== history length 10 ===
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 10/11
direction agreement: 2/10
new directions: {'left': 3, 'forward': 2, 'turn_left': 2, 'right': 3}
oscillation rate: new 0.22 / logged 0.10
first 'done' at decision: never
latency s: mean 9.79 max 15.76
  mismatch @1757597485: logged right -> new left
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new turn_left
  mismatch @1757598192: logged stop -> new right
  mismatch @1757600433: logged forward -> new right
  mismatch @1757600474: logged forward -> new left
  mismatch @1757600585: logged forward -> new right
  mismatch @1757600683: logged forward -> new left
```
### rq6_blank_instr
```
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 10/11
direction agreement: 4/10
new directions: {'right': 1, 'forward': 3, 'turn_left': 4, 'stop': 1, 'left': 1}
oscillation rate: new 0.00 / logged 0.10
first 'done' at decision: 7
latency s: mean 9.29 max 14.91
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new turn_left
  mismatch @1757598192: logged stop -> new turn_left
  mismatch @1757600474: logged forward -> new stop
  mismatch @1757600526: logged forward -> new turn_left
  mismatch @1757600683: logged forward -> new left
```
### rq6_grey_frames
```
cases: 11
logged directions: {'right': 2, 'forward': 7, 'left': 1, 'stop': 1}
logged mean confidence: 0.84
replayed: 11 (skipped 0 without frames)
valid JSON: 11/11
direction agreement: 2/11
new directions: {'right': 2, 'forward': 1, 'turn_left': 3, 'stop': 1, 'left': 4}
oscillation rate: new 0.20 / logged 0.10
first 'done' at decision: never
latency s: mean 7.71 max 36.40
  mismatch @1757597708: logged right -> new turn_left
  mismatch @1757597792: logged left -> new turn_left
  mismatch @1757598192: logged stop -> new turn_left
  mismatch @1757600433: logged forward -> new stop
  mismatch @1757600474: logged forward -> new left
  mismatch @1757600526: logged forward -> new right
  mismatch @1757600585: logged forward -> new left
  mismatch @1757600639: logged forward -> new left
  mismatch @1757600683: logged forward -> new left
```
### rq7_models
```
model                                    valid  agree  osc   done  lat_mean  lat_max
qwen2.5vl:3b                              1.00   0.18  0.20     6     11.22    15.93
```
