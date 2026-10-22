# ArduSub ROV Automatic Control System

A Python control system for ArduSub underwater ROVs. It replaces an external joystick and lets an algorithm, such as a vision-language-action (VLA) model, drive the vehicle.

## Features

- **MAVLink communication**: talks to ArduSub over the MAVLink protocol
- **Virtual joystick**: simulates joystick input from the keyboard
- **Automatic control**: built-in PID and MPC controllers with depth hold and heading hold
- **Safety**: depth limits, emergency stop and related protections
- **Mode switching**: switch between manual and automatic control
- **VLA command execution**: executes discrete motion commands from a vision-language-action model
- **Extensible**: easy to plug in your own control algorithms

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Virtual Joystick │───▶│ Main Controller │───▶│ MAVLink Interface│
│ VirtualJoystick │    │ MainController  │    │ MavlinkInterface│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Auto Controller │
                       │ AutoController  │
                       └─────────────────┘
```

## MPC Controller

The system includes a zero-data motion execution module based on Model Predictive Control (MPC) that executes discrete VLA motion commands:

### Motion Axes
Each VLA direction maps to one ArduSub RC channel; only that axis is driven for the duration of the command:
- **`forward` / `backward`**: fore/aft (channel 5)
- **`left` / `right`**: strafe (channel 6)
- **`up` / `down`**: vertical (channel 3, overrides depth hold while active)
- **`turn_left` / `turn_right`**: yaw in place (channel 4, added on top of heading hold)
- **`stop`**: zero output

Translational directions follow a constrained time-optimal velocity trajectory; turns follow the same shape as an angular-rate trajectory. Speed is one of `low`, `medium`, `high`.

### Hydrodynamic Compensation
- Online estimate of translational and rotational drag
- Drag compensation in the control law
- Adapts to different underwater environments

### Timing
- Strict 1-second motion execution window per command
- 20 ms control update interval
- Reference trajectory tracking

## Installation

### Requirements
- Python 3.7+
- Windows/Linux/macOS

### Dependencies
```bash
pip install -r requirements.txt
```

### Main Dependencies
- `pymavlink`: MAVLink communication
- `pygame`: virtual joystick support
- `keyboard`: keyboard monitoring
- `numpy`: numerical computing
- `opencv-python`: computer vision support (optional)

## Configuration

### config.ini
```ini
[Connection]
connection_type = udp          # Connection type: udp or serial
udp_host = 127.0.0.1           # UDP host address
udp_port = 14445               # UDP port
serial_port = COM3             # Serial port
baud_rate = 115200             # Baud rate

[Control]
control_frequency = 10         # Control frequency (Hz)
max_throttle = 100             # Maximum throttle percentage
max_yaw_rate = 45              # Maximum yaw rate (deg/s)
max_pitch_angle = 30           # Maximum pitch angle (deg)
max_roll_angle = 30            # Maximum roll angle (deg)

[AutoControl]
enable_depth_hold = true       # Enable depth hold
target_depth = -2.0            # Target depth (m)
depth_tolerance = 0.1          # Depth tolerance (m)
enable_heading_hold = true     # Enable heading hold
target_heading = 0             # Target heading (deg)
heading_tolerance = 5          # Heading tolerance (deg)

[Safety]
emergency_stop_timeout = 5.0   # Emergency stop timeout (s)
max_depth = -10.0              # Maximum depth limit (m)
min_depth = -0.5               # Minimum depth limit (m)
```

The `[MPC]` section is optional; the defaults below are used when it is absent:
```ini
[MPC]
beta = 1.0                     # Tracking error weight
gamma = 0.1                    # Control effort weight
delta = 0.05                   # Hydrodynamic drag weight
mass = 10.0                    # Vehicle mass (kg)
inertia = 0.5                  # Moment of inertia (kg·m²)
translational_drag_coeff = 5.0 # Translational drag coefficient
rotational_drag_coeff = 0.1    # Rotational drag coefficient
```

## Usage

### 1. Basic Startup
```bash
python main_controller.py
```

### 2. Running the Examples
```bash
python example_usage.py
```

### 3. Manual Control
The system starts in manual control mode:
- **W/S**: pitch (forward/backward)
- **A/D**: roll (left/right)
- **Q/E**: yaw (left/right)
- **Space/Shift**: throttle (up/down)
- **R**: reset all controls
- **ESC**: emergency stop
- **M**: toggle manual/automatic mode

### 4. Automatic Control
```python
from main_controller import ROVMainController

# Create the controller
controller = ROVMainController()

# Start
controller.start()

# Switch to automatic mode
controller.set_control_mode('auto')

# Set targets
controller.set_target_depth(-2.0)    # target depth 2 m
controller.set_target_heading(90.0)  # target heading 90 degrees

# Shut down
controller.shutdown()
```

### 5. Executing VLA Commands
```python
# Execute a VLA command (from a vision-language-action model)
vla_command = {
    "reasoning": "avoid obstacle",
    "action": {
        "direction": "forward",   # forward/backward/left/right/up/down/turn_left/turn_right/stop
        "speed": "medium",        # low/medium/high
        "confidence": 0.9
    },
    "status": "in progress"
}

controller.execute_vla_command(vla_command)
```

## How the MPC Controller Works

### Time-Constrained Motion Trajectory
For a translational command the controller generates this velocity reference:
```
v(t) = 
  v_cmd * min(5t, 1)        0 ≤ t < 0.2s
  v_cmd                     0.2 ≤ t < 0.5s
  v_cmd * max(1-2(t-0.5), 0) 0.5 ≤ t ≤ 1s
```

For a turn command the controller generates the same shape as an angular-rate reference.

### Hydrodynamics-Aware MPC
The controller computes thrust by solving:
```
min ∫[0,1] {β||v-v_ref||² + γ||τ||² + δ||F_drag,v||²} dt  (translational)
min ∫[0,1] {β||θ-θ_ref||² + γ||τ||² + δ||τ_drag,r||²} dt  (rotational)
```

Drag is modelled as:
```
F_drag,v = D_v * v|v|
τ_drag,r = D_r * r|r|
```

### Online Drag Estimation
The drag coefficients are estimated online with:
```
D_v = (τ_v - M*v_dot) / (v|v|)
D_r = (τ_r - I_z*r_dot) / (r|r|)
```

The current implementation is a simplified proportional controller with drag compensation; the three translational axes share the forward velocity feedback, so lateral and vertical motion degrade to open loop when no dedicated velocity measurement is available.

## Custom Algorithm Integration

### 1. Subclass AutoController
```python
from auto_controller import AutoController

class MyCustomController(AutoController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # Custom initialization
    
    def _execute_auto_control(self):
        # Implement your algorithm here
        # e.g. vision-based target tracking
        # e.g. sonar-based obstacle avoidance
        pass
```

### 2. Plug It Into the Main Controller
```python
from main_controller import ROVMainController

class CustomROVController(ROVMainController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # Swap in the custom controller
        self.auto_controller = MyCustomController(config_file)
```

## Safety Notes

1. **Depth limit**: exceeding `max_depth` triggers an emergency stop; being shallower than `min_depth` only logs, so the ROV can dive from the surface
2. **Emergency stop**: triggered by ESC or when an anomaly is detected
3. **Connection monitoring**: the MAVLink link is monitored and reconnected when lost
4. **Timeout protection**: normal control resumes after the emergency stop timeout

## Troubleshooting

### Common Issues

1. **MAVLink connection fails**
   - Check that QGroundControl is running
   - Confirm the UDP port settings
   - Check firewall settings

2. **Controls do not respond**
   - Confirm the ROV is armed
   - Check the control mode
   - Check the log file

3. **Unstable automatic control**
   - Tune the PID gains
   - Check the sensor data
   - Confirm the targets are reasonable

### Log File
The system writes `rov_control.log` while running, with detailed runtime information and errors.

## Development

### Code Structure
```
QGC/
├── requirements.txt           # Dependency list
├── config.ini                 # Configuration file
├── mavlink_interface.py       # MAVLink communication interface
├── auto_controller.py         # Automatic controller (PID + MPC)
├── virtual_joystick.py        # Virtual joystick
├── main_controller.py         # Main controller
├── example_usage.py           # Usage examples
├── joy.py                     # vJoy virtual gamepad driver (Windows)
├── RovController.py           # Simulated ROV controller (prints only)
├── rov_movement.py            # Timed movement helper on top of RovController
├── debug_mavlink.py           # MAVLink message monitor
├── test_ardusub_connection.py # Connection and control command test
├── test_vjoy_controller.py    # vJoy device test
└── README.md                  # Documentation
```

### Extending
1. **New control algorithms**: subclass AutoController
2. **New sensors**: extend MavlinkInterface
3. **Custom control interface**: extend VirtualJoystick
4. **New safety features**: add them to the main controller

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

Issues and pull requests are welcome.

## Contact

Questions or suggestions:
- Open a GitHub issue
- Email the project maintainers

---

**Note**: when using this system to control an ROV, make sure you are in a safe environment and follow the relevant underwater operation rules.
