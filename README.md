# Dual Brain VLA Controller

[![CI](https://github.com/wuisabel-gif/UnderwaterVLA/actions/workflows/ci.yml/badge.svg)](https://github.com/wuisabel-gif/UnderwaterVLA/actions/workflows/ci.yml)

Community continuation of the dual-brain underwater VLA controller from the paper
[UnderwaterVLA (arXiv:2509.22441)](https://arxiv.org/abs/2509.22441). The code here
started from the authors' anonymous release and has since been wired to a camera feed
and the ArduSub stack, made fully autonomous, tested, and translated to English.
See [Attribution](#attribution-and-license) below.

This project implements a dual-brain architecture for controlling an underwater robot using vision-language-action (VLA) models. It consists of two main components: a "Big Brain" for high-level task planning and a "Small Brain" for low-level execution decisions.

## Project Structure

- `dual_brain_core.py`: Core implementation of the BigBrain and SmallBrain classes
- `dual_brain_oop.py`: Object-oriented controller that coordinates the two brains
- `QGC/`: Directory containing the ROV control system

## Components

### Big Brain (Task Planning)
The BigBrain class is responsible for high-level task planning. It:
- Takes screenshots of the environment
- Sends images and instructions to the QVQmax API
- Generates detailed task plans with multiple steps
- Outputs plans in a structured JSON format

### Small Brain (Execution Decisions)
The SmallBrain class handles low-level execution decisions. It:
- Receives task plans from the BigBrain
- Makes real-time decisions based on current images
- Outputs movement commands (direction, speed) in JSON format
- Logs decisions to a file

### Dual Brain Controller
The DualBrainController class coordinates the interaction between the BigBrain and SmallBrain:
- Captures images from the screen
- Requests task plans from the BigBrain
- Sends plans to the SmallBrain for execution
- Continues execution until the task is completed

### ROV Control System (QGC/)
The ROV control system interfaces with the ArduSub firmware to control the physical ROV:
- Integrates with the MPC controller for precise motion execution
- Processes VLA commands from the SmallBrain
- Provides safety features like depth limiting and emergency stop
- Supports both manual and autonomous control modes

## JSON Output Formats

### Big Brain Output Format
```json
{
  "reasoning": "string (analysis and thought process for the task)",
  "task_plan": [
    {
      "step": "integer (step number)",
      "description": "string (detailed description of the step)",
      "target_object": "string (target object)",
      "obstacle_to_avoid": "string (obstacles to avoid)",
      "confidence": "float [0.0-1.0] (confidence in the plan)"
    }
  ],
  "total_steps": "integer (total number of steps > 1)",
  "estimated_completion_time": "string (estimated completion time)"
}
```

### Small Brain Output Format
```json
{
  "reasoning": "string (thought process and reasoning for the decision)",
  "action": {
    "direction": "string (enum: ['forward','backward','left','right','up','down','turn_left','turn_right','stop'])",
    "speed": "string (enum: ['low','medium','high','stop'])",
    "confidence": "float [0.0-1.0]"
  },
  "status": "string (enum: ['in_progress', 'done'])",
  "step_completed": "boolean (optional, whether the step is completed)"
}
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in QVQMAX_API_KEY and the LM Studio endpoint
```

Credentials and endpoints are read from environment variables (`QVQMAX_API_KEY`,
`QVQMAX_API_URL`, `LMSTUDIO_API_URL`, `LMSTUDIO_MODEL`). Nothing is hardcoded.

`left`/`right` strafe sideways; `turn_left`/`turn_right` yaw in place; `up`/`down` are vertical.
Old logs or a model that answers in Chinese are normalised through `rov_backend.LEGACY_DIRECTIONS` / `LEGACY_STATUS`.

## Usage

`run_vla.py` wires the brains to an image source and an execution backend:

```bash
# Screen capture + print-only simulation (original behaviour)
python run_vla.py --instruction exp1

# USB camera + simulation (verify the camera on the bench first)
python run_vla.py --source camera:0 --instruction "Swim through the hula hoop"

# BlueROV video stream + real ArduSub over MAVLink (see QGC/config.ini)
python run_vla.py --source udp://192.168.2.1:5600 --backend ardusub --instruction exp2
```

Omit `--instruction` for the interactive prompt. Other flags: `--settle` (seconds to
wait after each action before capturing), `--max-steps` (hard cap per task),
`--no-planner` (skip the cloud planner), `--interactive` (confirm each action),
`--min-confidence` (actions below it become stop, default 0.5), `--decision-timeout`
(seconds to wait for the small brain before stopping the ROV, default 30).

### Image sources (`image_source.py`)
- `screen` – screenshot rotated 90° clockwise, the original behaviour
- `camera:<index>` / `camera:<file>` / `udp://…` / `rtsp://…` – OpenCV capture

### Execution backends (`rov_backend.py`)
- `sim` – prints the motion via the `RovMovement` stub
- `ardusub` – headless MAVLink + MPC loop from `QGC/`, blocks until each action finishes

## Offline replay (`replay.py`)

Re-run the small brain over logged decisions and the screenshots in `FIG/` without
putting the ROV in the water. Useful for comparing prompts or models.

```bash
python replay.py --instruction exp1 --dry-run   # just summarise the log
python replay.py --instruction exp1 --out replay.json
```

Reports logged direction counts, JSON validity, direction agreement with the log,
and model latency.

## Tests

```bash
python3 -m unittest discover -s tests
```

`tests/test_mavlink_integration.py` drives `ArduSubBackend` over a real MAVLink UDP link
against a fake vehicle that answers heartbeats and records `RC_CHANNELS_OVERRIDE`, so the
whole QGC path is checked in CI without an ArduPilot build. It is skipped when
`pymavlink` is not installed.

## Attribution and license

- **Paper:** *UnderwaterVLA*, [arXiv:2509.22441](https://arxiv.org/abs/2509.22441). All
  credit for the dual-brain design, the prompts and the original experiments goes to its authors.
- **Original code:** the anonymous release at
  <https://anonymous.4open.science/r/UnderwaterVLA-8FC8>. The initial commit of this
  repository is that release with the hardcoded API key removed.
- **This repository:** everything after the initial commit is independent work and is
  released under the [MIT License](LICENSE). The anonymous release ships no license file
  (its QGC README states MIT); if you are one of the original authors and would like
  different attribution or licensing, please open an issue.
- Not affiliated with or endorsed by the paper's authors.
