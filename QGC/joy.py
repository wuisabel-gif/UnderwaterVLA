import pyvjoy
import time
import json

# Direction -> (axis, sign). Which physical stick each vJoy axis means is decided by the
# joystick calibration in QGroundControl; the defaults here follow its usual ArduSub layout:
# y = forward/backward, x = lateral strafe, z = vertical, rx = yaw.
DIRECTION_MAP = {
    'forward': ('y', -1.0), 'backward': ('y', 1.0),
    'left': ('x', -1.0), 'right': ('x', 1.0),
    'up': ('z', -1.0), 'down': ('z', 1.0),
    'turn_left': ('rx', -1.0), 'turn_right': ('rx', 1.0),
    'stop': ('y', 0.0),
}
MOTION_AXES = ('x', 'y', 'z', 'rx')


class VJoyController:
    def __init__(self, device_id=1):
        """
        Initialize the virtual joystick
        :param device_id: vJoy device ID (default 1)
        """
        try:
            self.device = pyvjoy.VJoyDevice(device_id)
            self.reset()
            print("vJoy device initialized")
        except Exception as e:
            raise RuntimeError(f"vJoy initialization failed: {e}")

    def reset(self):
        """Reset the stick and button state"""
        self.device.reset()
        self.device.update()

    def set_axis(self, axis, value):
        """
        Set a stick axis value (normalized range: -1.0 to 1.0)
        :param axis: axis name (e.g. 'x', 'y', 'rx', 'ry')
        :param value: normalized value (mapped to vJoy's 1-32768 range)
        """
        axis_map = {
            'x': pyvjoy.HID_USAGE_X,
            'y': pyvjoy.HID_USAGE_Y,
            'z': pyvjoy.HID_USAGE_Z,
            'rx': pyvjoy.HID_USAGE_RX,
            'ry': pyvjoy.HID_USAGE_RY,
            'rz': pyvjoy.HID_USAGE_RZ,
        }
        if axis not in axis_map:
            raise ValueError(f"Unsupported axis name: {axis}")

        # Map the normalized value (-1~1) to vJoy's 1-32768 range
        scaled_value = int((value + 1) * 16384)  # 16384 = 32768/2
        self.device.set_axis(axis_map[axis], scaled_value)

    def press_button(self, button_id, state=True):
        """
        Press/release a button
        :param button_id: button number (starting at 1)
        :param state: True (pressed) or False (released)
        """
        self.device.set_button(button_id, state)

    def update(self):
        """Commit the current input state"""
        self.device.update()

    def close(self):
        """Close the device"""
        self.reset()
        self.device = None

    def execute_from_json(self, json_input):
        """
        Extract the speed and direction from JSON input and perform the matching action
        :param json_input: JSON string or dict containing direction and speed
        """
        # Parse a string input into a dict
        if isinstance(json_input, str):
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON input: {e}")
        elif isinstance(json_input, dict):
            data = json_input
        else:
            raise TypeError("Input must be a JSON string or a dict")

        # Extract the action
        action = data.get('action', {})
        direction = action.get('direction')
        speed = action.get('speed')

        # Speed -> value map
        speed_map = {
            'low': 0.3,
            'medium': 0.8,
            'high': 1.0,
            'stop': 0.0
        }

        # Reset the device
        self.reset()

        if direction not in DIRECTION_MAP or speed not in speed_map:
            raise ValueError("Invalid direction or speed value")
        for axis in MOTION_AXES:
            self.set_axis(axis, 0.0)
        axis, sign = DIRECTION_MAP[direction]
        self.set_axis(axis, sign * speed_map[speed])

        # Commit the input state
        self.update()
        print(f"Executing action: direction={direction}, speed={speed}")

# Example usage
if __name__ == "__main__":
    # Initialize the virtual joystick
    controller = VJoyController()

    # Example JSON input
    json_input = {
        "reasoning": "Move forward, avoiding obstacles",
        "action": {
            "direction": "forward",
            "speed": "medium",
            "confidence": 0.9
        },
        "status": "in progress",
        "step_completed": True
    }

    # Execute the action
    controller.execute_from_json(json_input)

    # Hold the state for 2 seconds, then release
    time.sleep(2)
    controller.reset()
    controller.close()