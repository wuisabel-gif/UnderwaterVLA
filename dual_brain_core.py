import base64
import collections
import json
import time
import os
from openai import OpenAI
from image_source import ScreenSource, make_image_source, encode_image
from rov_backend import RovBackend, SimulatedBackend, make_backend, LEGACY_DIRECTIONS


class BaseBrain:
    """Base class with the methods shared by the big brain and the small brain"""
    
    # Configuration
    # All credentials and endpoints come from environment variables so no secrets land in the repo
    QVQMAX_API_URL = os.environ.get("QVQMAX_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QVQMAX_API_KEY = os.environ.get("QVQMAX_API_KEY", "")
    LMSTUDIO_API_URL = os.environ.get("LMSTUDIO_API_URL", "http://127.0.0.1:1234/v1")
    LMSTUDIO_API_KEY = os.environ.get("LMSTUDIO_API_KEY", "lm-studio")
    LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "qwen2.5-vl-7b-instruct")
    
    def __init__(self):
        # Preset instructions
        self.preset_instructions = {
            "exp1": "Go to the farthest pillar without touching any obstacle. Output the next action strictly in the JSON format shown in the example.",
            "exp2": "Swim through the hula hoop",
            "exp3": "Predict the fish's trajectory and avoid it"
        }
    
    # Default image source: screen capture (original behaviour). set_image_source switches to a
    # camera/video stream; all Brain instances share the same source.
    _image_source = None

    @classmethod
    def set_image_source(cls, source):
        """Set the global image source (an ImageSource instance, or a string accepted by make_image_source)"""
        if isinstance(source, str):
            source = make_image_source(source)
        cls._image_source = source

    @classmethod
    def get_image_source(cls):
        if cls._image_source is None:
            cls._image_source = ScreenSource()
        return cls._image_source

    def encode_image_to_base64(self):
        """
        Grab one frame from the current image source, save it as a PNG and return it base64-encoded
        Returns: (base64_string, filename) tuple; (None, None) on failure
        """
        try:
            img = self.get_image_source().capture()
            base64_string, filename = encode_image(img)
            print(f"Frame captured, saved as: {filename}")
            return base64_string, filename
        except Exception as e:
            print(f"Frame capture failed: {e}")
            return None, None

    def log_decision(self, decision):
        # Append the decision to the log
        # Build a log entry with a timestamp and the decision
        log_entry = {
            "timestamp": time.time(),
            "decision": decision
        }
        # Append the entry to the log file
        try:
            with open("decision_log.json", "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Error writing decision log: {e}")



class BigBrain(BaseBrain):
    """Big brain: responsible for task planning"""
    
    def call_qvqmax_api_for_planning(self, image_base64, instruction, image_base64_2=None):
        # Call the QVQmax cloud big-brain API to generate a task plan
        #
        # Args:
        #     image_base64 (str): base64 encoding of the first image
        #     instruction (str): instruction text
        #     image_base64_2 (str, optional): base64 encoding of the second image, default None
        #
        # Returns:
        #     dict or None: the parsed JSON object from the API response, None on failure
        reasoning_content = ""  # full reasoning trace
        answer_content = ""     # full answer
        is_answering = False   # whether reasoning has ended and the answer has started
        # Initialise the OpenAI client
        client = OpenAI(
            api_key=self.QVQMAX_API_KEY,
            base_url=self.QVQMAX_API_URL
        )
        
        # Build the user content; one or two images are supported
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        # Add the second image if one was given
        if image_base64_2:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64_2}"
                }
            })
        
        # Add the instruction text
        user_content.append({
            "type": "text",
            "text": instruction
        })
        
        # System prompt for big-brain planning
        planning_system_prompt = {
            "role": "underwater_robot_task_planner",
            "description": "You are a task-planning expert for underwater scenes. Based on the images and the instruction, produce a detailed multi-step task execution plan.",
            "rules": [
                "Carefully analyse the environment and obstacles in the images",
                "Build a multi-step execution plan from the user's instruction",
                "Each step must state a concrete operation and goal",
                "The plan must account for safety and efficiency",
                "Output the result as standard JSON"
            ],
            "input_format": {
                "image": "base64 encoded JPEG image (single or multiple views)",
                "instruction": "string"
            },
            "output_format": {
                "reasoning":"string (analysis and thought process for the task)",
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
        }

        messages = [
            {
                "role": "system",
                "content": json.dumps(planning_system_prompt, ensure_ascii=False)
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        

        # Create the chat completion request
        completion = client.chat.completions.create(
            model="qwen-vl-max-latest",
            messages=messages,
            stream=True,
            temperature=0.9,  # moderate creativity
            max_tokens=800,   # allow a longer plan description
        )
        
        # Read the response
        for chunk in completion:
            # If chunk.choices is empty, print the usage
            if not chunk.choices:
                print("\nUsage:")
                print(chunk.usage)
            else:
                delta = chunk.choices[0].delta
                # Print the reasoning trace
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content != None:
                    print(delta.reasoning_content, end='', flush=True)
                    reasoning_content += delta.reasoning_content
                else:
                    # Answer starts
                    if delta.content != "" and is_answering is False:
                        print("\n" + "=" * 20 + "Full answer" + "=" * 20 + "\n")
                        is_answering = True
                    # Print the answer as it streams
                    print(delta.content, end='', flush=True)
                    answer_content += delta.content


        if answer_content:
            try:
                # Strip a possible markdown code fence
                cleaned_output = answer_content.strip()
                if cleaned_output.startswith("```json"):
                    # Remove the leading ```json and trailing ```
                    cleaned_output = cleaned_output[7:].strip()
                    if cleaned_output.endswith("```"):
                        cleaned_output = cleaned_output[:-3].strip()
                elif cleaned_output.startswith("```"):
                    # Remove the leading ``` and trailing ```
                    cleaned_output = cleaned_output[3:].strip()
                    if cleaned_output.endswith("```"):
                        cleaned_output = cleaned_output[:-3].strip()
                return json.loads(cleaned_output)
            except json.JSONDecodeError:
                print(f"QVQmax Planning API returned invalid JSON: {answer_content}")
                return None
        else:
            print("QVQmax Planning API returned empty output")
            return None


class SmallBrain(BaseBrain):
    """Small brain: responsible for execution decisions"""
    
    def __init__(self, backend: RovBackend = None, settle_time: float = 2.0,
                 frame_gap: float = 1.0, interactive: bool = False, capture_retries: int = 5,
                 min_confidence: float = 0.5, decision_timeout: float = 30.0, history_len: int = 5):
        super().__init__()
        # Last few executed actions, sent to the model so it can reason over the sequence.
        self.history = collections.deque(maxlen=history_len)
        # Actions with confidence below this become stop; a missing confidence counts as 0
        self.min_confidence = min_confidence
        # Max seconds to wait for one small-brain call; on timeout it returns None (the caller stops the ROV)
        self.decision_timeout = decision_timeout
        # Execution backend: print-only simulation by default; pass make_backend("ardusub") to drive a real ROV
        self.backend = backend if backend is not None else SimulatedBackend()
        # How long to wait after an action before capturing (lets the water/picture settle)
        self.settle_time = settle_time
        # Gap between the two frames, gives the small brain temporal information
        self.frame_gap = frame_gap
        # True: confirm each action with Enter (original behaviour); False: fully automatic
        self.interactive = interactive
        self.capture_retries = capture_retries

    def capture_pair(self):
        """Capture two frames frame_gap seconds apart and return (base64_1, base64_2). Raises RuntimeError after the retries are exhausted."""
        for attempt in range(1, self.capture_retries + 1):
            b64_1, _ = self.encode_image_to_base64()
            time.sleep(self.frame_gap)
            b64_2, _ = self.encode_image_to_base64()
            if b64_1 and b64_2:
                return b64_1, b64_2
            print(f"Frame capture failed, retry {attempt}/{self.capture_retries}")
            time.sleep(1)
        raise RuntimeError("Repeated frame capture failures, cannot continue")
    
    def call_lmstudio_api(self, image_base64, instruction, task_plan=None, current_step=None, image_base64_2=None):
        # Call the local LM Studio small-brain API
        #
        # Args:
        #     image_base64 (str): base64 encoding of the first image
        #     instruction (str): instruction text
        #     task_plan (dict, optional): task plan produced by the big brain
        #     current_step (int, optional): step currently being executed
        #     image_base64_2 (str, optional): base64 encoding of the second image, default None
        #
        # Returns:
        #     dict or None: the parsed JSON object from the API response, None on failure
        
        # Initialise the OpenAI client
        client = OpenAI(
            api_key=self.LMSTUDIO_API_KEY,
            base_url=self.LMSTUDIO_API_URL
        )
        
        # Build the user content; one or two images are supported
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        # Add the second image if one was given
        if image_base64_2:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64_2}"
                }
            })
        
        # Add the instruction text and the task plan (if any)
        text_content = f"Instruction: {instruction}"
        if task_plan and current_step is not None:
            text_content += f"\nTask plan: {json.dumps(task_plan, ensure_ascii=False)}"
            text_content += f"\nCurrent step: {current_step}"
        if self.history:
            text_content += f"\nRecent actions (oldest->newest): {json.dumps(list(self.history), ensure_ascii=False)}"
            
        user_content.append({
            "type": "text",
            "text": text_content
        })
        
        # System prompt for small-brain decisions
        decision_system_prompt = {
            "role": "underwater_robot_vla_navigator",
            "description": "You are a pure vision-language-action (VLA) decision model for underwater scenes. You produce motion commands from real-time image analysis and natural-language instructions, and you recall the time sequence of previous images when deciding. Follow these rules strictly:",
            "rules": [
                "The only visual input is monocular RGB images",
                "Always interpret the task goal together with the user's instruction",
                "If a task plan is given, follow the current step; if you judge that the previous step is not finished yet, keep executing the previous step and add a step_completed: true field to the output",
                "The recent actions in the input are the sequence you already executed; judge their effect from the two frames and avoid repeating useless actions or oscillating back and forth",
                "Every decision must pick one of the nine basic actions [forward, backward, left, right, up, down, turn_left, turn_right, stop]; left/right are a sideways strafe, turn_left/turn_right are yaw in place",
                "Every decision must pick one of the four basic speeds ['low','medium','high','stop']",
                "Output strictly as standard JSON, with no extra text",
                "Output status in_progress while you consider the task unfinished; output done and stop once the task is complete",
            ],
            "input_format": {
                "image": "base64 encoded JPEG image (single or multiple views)",
                "instruction": "string",
                "task_plan": "optional task plan from brain",
                "current_step": "optional current step number"
            },
            "output_format": {
                "reasoning": "string (thought process about the images and the reason for the decision)",
                "action": {
                    "direction": "string (enum: ['forward','backward','left','right','up','down','turn_left','turn_right','stop'])",
                    "speed": "string (enum: ['low','medium','high','stop'])",
                    "confidence": "float [0.0-1.0]"
                },
                "status": "string (enum: ['in_progress', 'done'])",
                "step_completed": "boolean (optional, whether the step is completed)"
            }
        }
        
        messages = [
            {
                "role": "system",
                "content": json.dumps(decision_system_prompt, ensure_ascii=False)
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        
        try:
            # Create the chat completion request
            completion = client.chat.completions.create(
                model=self.LMSTUDIO_MODEL,
                messages=messages,
                stream=False,
                temperature=0.5,  # low temperature for fairly deterministic output
                max_tokens=500,
                timeout=self.decision_timeout,
            )
            
            # Read the response
            response_content = completion.choices[0].message.content if completion.choices else None
            if response_content:
                try:
                    # Strip a possible markdown code fence
                    cleaned_output = response_content.strip()
                    if cleaned_output.startswith("```json"):
                        # Remove the leading ```json and trailing ```
                        cleaned_output = cleaned_output[7:].strip()
                        if cleaned_output.endswith("```"):
                            cleaned_output = cleaned_output[:-3].strip()
                    elif cleaned_output.startswith("```"):
                        # Remove the leading ``` and trailing ```
                        cleaned_output = cleaned_output[3:].strip()
                        if cleaned_output.endswith("```"):
                            cleaned_output = cleaned_output[:-3].strip()
                    return json.loads(cleaned_output)
                except json.JSONDecodeError:
                    print(f"LM Studio API returned invalid JSON: {response_content}")
                    return None
            else:
                print("LM Studio API returned empty output")
                return None
                
        except Exception as e:
            print(f"Error calling LM Studio API: {e}")
            return None

    def execute_decision(self, decision):
        # Execute the decision (hand it to the backend; the default backend only prints)
        # Log the decision first
        self.log_decision(decision)
        print("Executing decision:")
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        action = decision.get('action', {})
        direction = LEGACY_DIRECTIONS.get(action.get('direction'), action.get('direction'))
        speed = action.get('speed')
        confidence = action.get('confidence')
        if not isinstance(confidence, (int, float)) or confidence < self.min_confidence:
            print(f"Confidence {confidence!r} below threshold {self.min_confidence}, stopping instead")
            direction, speed = 'stop', 'stop'

        self.history.append({"direction": direction, "speed": speed,
                             "step_completed": decision.get("step_completed", True)})

        # Hand over to the execution backend (blocks until the action finishes)
        try:
            self.backend.execute(direction, speed)
        except ValueError as e:
            print(f"Invalid action, stopping instead: {e}")
            self.backend.stop()

        if self.interactive:
            input("Press Enter to confirm the action has finished...")
        if self.settle_time > 0:
            print(f"Waiting {self.settle_time}s before capturing")
            time.sleep(self.settle_time)
        image_base64_1, image_base64_2 = self.capture_pair()

        # Return the encoded images for the next decision
        return image_base64_1, image_base64_2
