import json
import time
from dual_brain_core import BigBrain, SmallBrain, BaseBrain
from rov_backend import LEGACY_STATUS


class DualBrainController:
    """Dual-brain controller: coordinates the big brain and the small brain"""

    def __init__(self, backend=None, image_source=None, settle_time: float = 2.0,
                 interactive: bool = False, max_steps: int = 50, use_planner: bool = True,
                 min_confidence: float = 0.5, decision_timeout: float = 30.0):
        """
        Args:
            backend: rov_backend.RovBackend instance (None = print-only simulation)
            image_source: image_source.ImageSource instance or string (None = screen capture)
            settle_time: seconds to wait after each action before capturing
            interactive: True = confirm each action with Enter
            max_steps: max actions per task; past that the task is force-stopped
            use_planner: False = skip big-brain planning and let the small brain decide directly
        """
        if image_source is not None:
            BaseBrain.set_image_source(image_source)
        self.big_brain = BigBrain()
        self.small_brain = SmallBrain(backend=backend, settle_time=settle_time, interactive=interactive,
                                      min_confidence=min_confidence, decision_timeout=decision_timeout)
        self.max_steps = max_steps
        self.use_planner = use_planner

    def run_task_cycle(self, instruction):
        # Run one task cycle (planner then executor)
        self.small_brain.history.clear()  # history is per task

        try:
            image_base64_1, image_base64_2 = self.small_brain.capture_pair()
        except Exception as e:
            print(f"Frame capture failed: {e}")
            return None, True  # error signal, stop the loop
        
        # First ask the big brain for a task plan
        task_plan = None
        if self.use_planner:
            print("Generating task plan...")
            try:
                task_plan = self.big_brain.call_qvqmax_api_for_planning(image_base64_1, instruction, image_base64_2)
                self.big_brain.log_decision(task_plan)
            except Exception as e:
                print(f"Check that the QVQMAX API is reachable: {e}")
                task_plan = None
        if task_plan:
            print("Task plan generated:")
            print(json.dumps(task_plan, indent=2, ensure_ascii=False))
        else:
            print("Task plan generation failed, executing decisions directly")
        
        # Keep executing until the task is complete
        task_completed = False
        step_count = 1
        
        actions_taken = 0
        while not task_completed:
            if actions_taken >= self.max_steps:
                print(f"Reached the maximum number of actions {self.max_steps}, forcing stop")
                self.small_brain.backend.stop()
                return None, True
            actions_taken += 1
            print(f"\nExecuting step {step_count} (action {actions_taken})")
            
            # Only the small brain is called for the decision
            decision_response = self.small_brain.call_lmstudio_api(image_base64_1, instruction, task_plan, step_count, image_base64_2)
            
            # Execute the decision
            if decision_response:
                try:
                    image_base64_1, image_base64_2 = self.small_brain.execute_decision(decision_response)
                except Exception as e:
                    print(f"Execution or capture failed, stopping task: {e}")
                    self.small_brain.backend.stop()
                    return None, True
                
                # Check whether the task is complete
                status = decision_response.get('status', '')
                if LEGACY_STATUS.get(status, status) == 'done':
                    print("Task complete, leaving the loop")
                    task_completed = True
                    return decision_response, True  # task complete, stop the loop
                
                # Check whether the step is complete; if so, advance the step counter
                step_completed = decision_response.get('step_completed', True)
                if not step_completed:
                    print(f"Step {step_count} not complete")
                else:
                    step_count += 1
                

            else:
                print("Decision API call failed or timed out, no decision available.")
                # Default response so the program does not stop outright
                decision_response = {
                    "action": {
                        "direction": "stop",
                        "speed": "stop",
                        "confidence": 0.0
                    },
                    "status": "in_progress",
                    "reasoning": "API call failed, using the default stop command"
                }
                self.small_brain.backend.stop()
                return None, True  # error signal, stop the loop

    def run_task(self, instruction) -> bool:
        """Run one instruction until the model answers status 'done' or an error occurs. Returns whether it completed."""
        while True:
            decision_response, should_break = self.run_task_cycle(instruction)
            if should_break:
                status = decision_response.get('status') if decision_response else None
                done = LEGACY_STATUS.get(status, status) == 'done'
                if not done:
                    self.small_brain.backend.stop()
                return done
            time.sleep(1)

    def close(self):
        self.small_brain.backend.close()
        BaseBrain.get_image_source().close()

    def run(self):
        """Main loop (interactive command line)"""
        while True:
            # Outer loop: read an instruction from the keyboard
            print("\nEnter an instruction (type 'quit' to exit):")
            print("Preset instructions: exp1, exp2, exp3")
            user_input = input().strip()
            
            if user_input == 'quit':
                print("Exiting")
                break
                
            # Pick the instruction from the input
            if user_input in self.big_brain.preset_instructions:
                instruction = self.big_brain.preset_instructions[user_input]
                print(f"Selected preset instruction {user_input}: {instruction}")
                print("5s SHOOT")
                time.sleep(5)
            else:
                # Not a preset: use the input as a custom instruction
                instruction = user_input
                print(f"Using custom instruction: {instruction}")
                
            # Inner loop: run the task until the model answers 'done'
            done = self.run_task(instruction)
            print("Task complete" if done else "Task not complete (error or aborted)")


def main():
    controller = DualBrainController()
    try:
        controller.run()
    finally:
        controller.close()


if __name__ == "__main__":
    main()
