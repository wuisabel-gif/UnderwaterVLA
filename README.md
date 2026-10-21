# Dual Brain VLA Controller

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
    "direction": "string (enum: ['前','后','左','右','停'])",
    "speed": "string (enum: ['low','medium','high','stop'])",
    "confidence": "float [0.0-1.0]"
  },
  "status": "string (enum: ['任务中', '任务完成'])",
  "step_completed": "boolean (optional, whether the step is completed)"
}
```

## Usage

1. Run `python dual_brain_oop.py` to start the controller
2. Select a preset instruction or enter a custom one
3. The system will generate a task plan and execute it step by step
4. The ROVMainController in the QGC module will translate decisions into actual ROV movements