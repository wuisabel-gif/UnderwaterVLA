from RovController import RovController
import time

class RovMovement:
    def __init__(self):
        """Initialize the ROV movement controller"""
        self.controller = RovController()
        self.controller.arm()  # arm the ROV on startup

    def move(self, direction, speed, duration):
        """
        Move the ROV in the given direction at the given speed for the given time

        Args:
        direction (str): movement direction, one of:
            - 'forward' - move forward
            - 'backward' - move backward
            - 'left' - strafe left
            - 'right' - strafe right
            - 'up' - ascend
            - 'down' - descend
            - 'turn_left' - yaw left
            - 'turn_right' - yaw right
        speed (int): movement speed, range 0-1000
        duration (float): how long to move, in seconds
        """
        # Save the original speed
        original_speed = self.controller.default_speed

        try:
            # Apply the new speed
            self.controller.default_speed = min(max(speed, 0), 1000)

            # Pick the movement command for the direction
            movement_functions = {
                'forward': self.controller.move_forward,
                'backward': self.controller.move_backward,
                'left': self.controller.move_left,
                'right': self.controller.move_right,
                'up': self.controller.move_up,
                'down': self.controller.move_down,
                'turn_left': self.controller.turn_left,
                'turn_right': self.controller.turn_right
            }

            if direction not in movement_functions:
                raise ValueError(f"Invalid movement direction: {direction}")

            # Execute the movement
            movement_functions[direction]()

            # Wait for the requested duration
            time.sleep(duration)

            # Stop moving
            self.controller.stop()

        finally:
            # Restore the original speed
            self.controller.default_speed = original_speed

    def stop(self):
        """Stop all movement"""
        self.controller.stop()

    def close(self):
        """Shut down the controller and disarm the ROV"""
        self.controller.stop()
        self.controller.disarm()

# Usage example
if __name__ == "__main__":
    # Create the ROV movement controller
    rov = RovMovement()

    try:
        # Forward example: speed 500 for 2 seconds
        rov.move('forward', 500, 2)

        # Ascend example: speed 300 for 1.5 seconds
        rov.move('up', 300, 1.5)

        # Turn-left example: speed 400 for 1 second
        rov.move('turn_left', 400, 1)

    finally:
        # Make sure the controller is shut down cleanly on exit
        rov.close()