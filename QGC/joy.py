import pyvjoy
import time
import json

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

        # Direction -> axis map
        direction_map = {
            'forward': {'axis': 'y', 'value': -1.0},   # forward, negative Y
            'backward': {'axis': 'y', 'value': 1.0},   # backward, positive Y
            'left': {'axis': 'x', 'value': -1.0},      # strafe left, negative X
            'right': {'axis': 'x', 'value': 1.0},      # strafe right, positive X
            'stop': {'axis': 'y', 'value': 0.0}        # stop, all axes zeroed
        }

        # Speed -> value map
        speed_map = {
            'low': 0.3,
            'medium': 0.8,
            'high': 1.0,
            'stop': 0.0
        }

        # Reset the device
        self.reset()

        # A "stop" direction zeroes all axes
        if direction == 'stop':
            self.set_axis('x', 0.0)
            self.set_axis('y', 0.0)
        else:
            # Set the axis value from direction and speed
            if direction in direction_map and speed in speed_map:
                axis_info = direction_map[direction]
                speed_value = speed_map[speed]
                # Scale the axis value by the speed factor
                adjusted_value = axis_info['value'] * speed_value
                self.set_axis(axis_info['axis'], adjusted_value)

                # Diagonal movement might need X and Y set together;
                # this implementation assumes each basic direction is a single axis

            else:
                raise ValueError("Invalid direction or speed value")

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