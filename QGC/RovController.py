class RovController:
    def __init__(self):
        self.default_speed = 500
        print("Simulated ROV controller initialized")

    def arm(self):
        print("Simulated ROV armed")

    def disarm(self):
        print("Simulated ROV disarmed")

    def move_forward(self):
        print(f"Simulated ROV moving forward, speed: {self.default_speed}")

    def move_backward(self):
        print(f"Simulated ROV moving backward, speed: {self.default_speed}")

    def move_left(self):
        print(f"Simulated ROV strafing left, speed: {self.default_speed}")

    def move_right(self):
        print(f"Simulated ROV strafing right, speed: {self.default_speed}")

    def move_up(self):
        print(f"Simulated ROV ascending, speed: {self.default_speed}")

    def move_down(self):
        print(f"Simulated ROV descending, speed: {self.default_speed}")

    def turn_left(self):
        print(f"Simulated ROV turning left, speed: {self.default_speed}")

    def turn_right(self):
        print(f"Simulated ROV turning right, speed: {self.default_speed}")

    def stop(self):
        print("Simulated ROV stopped")