# ArduSub ROV Automatic Control System

This is a Python automatic control system for controlling ArduSub underwater ROVs, which can replace external joysticks and implement intelligent algorithmic automatic control.

## Features

- **MAVLink Communication**: Communicates with ArduSub through the MAVLink protocol
- **Virtual Joystick**: Simulates joystick input using keyboard
- **Automatic Control**: Built-in PID and MPC controllers, supports depth holding, heading holding, etc.
- **Safety Protection**: Depth limiting, emergency stop and other safety features
- **Mode Switching**: Supports switching between manual and automatic control modes
- **VLA Command Execution**: Supports execution of discrete motion commands from vision-language-action models
- **Extensible**: Easy to integrate custom intelligent algorithms

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Virtual Joystick │───▶│ Main Controller │───▶│ MAVLink Interface│
│   Module        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ Auto Controller │
                       │                 │
                       └─────────────────┘
```

## MPC Controller Features

The system integrates a zero-data motion execution module based on Model Predictive Control (MPC) that can precisely execute discrete motion commands from VLA models:

### Dual-Mode Motion Control
- **Translational Motion** (Forward/Backward): Generates constrained time-optimal velocity trajectories
- **Rotational Motion** (Left Turn/Right Turn): Generates constrained time-optimal angular velocity trajectories

### Hydrodynamic Compensation
- Real-time estimation of translational and rotational drag coefficients
- Compensation for fluid resistance in control optimization
- Adaptive to different underwater environments

### Precise Timing Control
- Strict 1-second motion execution cycle
- 20ms control update frequency
- Precise motion trajectory tracking

## Installation Requirements

### System Requirements
- Python 3.7+
- Windows/Linux/macOS

### Dependencies
```bash
pip install -r requirements.txt
```

### Main Dependencies
- `pymavlink`: MAVLink communication
- `pygame`: Virtual joystick support
- `keyboard`: Keyboard monitoring
- `numpy`: Numerical computing
- `opencv-python`: Computer vision support (optional)

## Configuration

### Connection Configuration (config.ini)
```ini
[Connection]
connection_type = udp          # Connection type: udp or serial
udp_host = 127.0.0.1         # UDP host address
udp_port = 14550              # UDP port
serial_port = COM3            # Serial port
baud_rate = 115200            # Baud rate

[Control]
control_frequency = 50        # Control frequency (Hz)
max_throttle = 100            # Maximum throttle percentage
max_yaw_rate = 45             # Maximum yaw rate (degrees/second)
max_pitch_angle = 30          # Maximum pitch angle (degrees)
max_roll_angle = 30           # Maximum roll angle (degrees)

[AutoControl]
enable_depth_hold = true      # Enable depth holding
target_depth = -2.0           # Target depth (meters)
depth_tolerance = 0.1         # Depth tolerance (meters)
enable_heading_hold = true    # Enable heading holding
target_heading = 0            # Target heading (degrees)
heading_tolerance = 5         # Heading tolerance (degrees)

[Safety]
emergency_stop_timeout = 5.0  # Emergency stop timeout (seconds)
max_depth = -10.0             # Maximum depth limit (meters)
min_depth = -0.5              # Minimum depth limit (meters)

[MPC]
beta = 1.0                    # Tracking error weight
gamma = 0.1                   # Control effort weight
delta = 0.05                  # Fluid resistance weight
mass = 10.0                   # System mass (kg)
inertia = 0.5                 # Moment of inertia (kg·m²)
translational_drag_coeff = 5.0 # Translational drag coefficient
rotational_drag_coeff = 0.1    # Rotational drag coefficient
```

## Usage

### 1. Basic Startup
```bash
python main_controller.py
```

### 2. Running Examples
```bash
python example_usage.py
```

### 3. Manual Control
After startup, the system defaults to manual control mode:
- **W/S**: Pitch control (forward/backward)
- **A/D**: Roll control (left/right)
- **Q/E**: Yaw control (left/right)
- **Space/Shift**: Throttle control (up/down)
- **R**: Reset all controls
- **ESC**: Emergency stop
- **M**: Switch between manual/automatic mode

### 4. Automatic Control
```python
from main_controller import ROVMainController

# Create controller
controller = ROVMainController()

# Start
controller.start()

# Switch to automatic mode
controller.set_control_mode('auto')

# Set targets
controller.set_target_depth(-2.0)    # Target depth 2 meters
controller.set_target_heading(90.0)  # Target heading 90 degrees

# Shutdown
controller.shutdown()
```

### 5. Executing VLA Commands
```python
# Execute VLA command (from vision-language-action model)
vla_command = {
    "reasoning": "avoid obstacle",
    "action": {
        "direction": "forward",
        "speed": "medium",
        "confidence": 0.9
    },
    "status": "in progress"
}

controller.execute_vla_command(vla_command)
```

## MPC Controller Working Principle

### Time-Constrained Motion Trajectory
For translational motion commands, the controller generates the following velocity trajectory:
```
v(t) = 
  v_cmd * min(5t, 1)        0 ≤ t < 0.2s
  v_cmd                     0.2 ≤ t < 0.5s
  v_cmd * max(1-2(t-0.5), 0) 0.5 ≤ t ≤ 1s
```

For rotational motion commands, the controller generates a similar angular velocity trajectory.

### Hydrodynamic-Aware MPC Formula
The controller calculates optimal thrust by solving the following optimization problem:
```
min ∫[0,1] {β||v-v_ref||² + γ||τ||² + δ||F_drag,v||²} dt  (translational)
min ∫[0,1] {β||θ-θ_ref||² + γ||τ||² + δ||τ_drag,r||²} dt  (rotational)
```

The drag terms are modeled as:
```
F_drag,v = D_v * v|v|
τ_drag,r = D_r * r|r|
```

### Real-Time Fluid Adaptation
The system estimates drag coefficients online using:
```
D_v = (τ_v - M*v_dot) / (v|v|)
D_r = (τ_r - I_z*r_dot) / (r|r|)
```

## Custom Algorithm Integration

### 1. Inheriting AutoController Class
```python
from auto_controller import AutoController

class MyCustomController(AutoController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # Add custom initialization code
    
    def _execute_auto_control(self):
        # Implement your intelligent algorithm
        # For example: vision-based target tracking
        # For example: sonar-based obstacle avoidance
        pass
```

### 2. Integration with Main Controller
```python
from main_controller import ROVMainController

class CustomROVController(ROVMainController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # Replace with custom controller
        self.auto_controller = MyCustomController(config_file)
```

## Safety Considerations

1. **Depth Limiting**: The system automatically limits the ROV's maximum and minimum depth
2. **Emergency Stop**: Automatically executes emergency stop when ESC key is pressed or anomalies are detected
3. **Connection Monitoring**: Automatically detects MAVLink connection status and reconnects when lost
4. **Timeout Protection**: Automatically recovers control after emergency stop

## Troubleshooting

### Common Issues

1. **MAVLink Connection Failure**
   - Check if QGroundControl is running
   - Confirm UDP port settings are correct
   - Check firewall settings

2. **Control Not Responding**
   - Confirm ROV is unlocked
   - Check control mode settings
   - View log files

3. **Unstable Automatic Control**
   - Adjust PID parameters
   - Check sensor data
   - Confirm target values are set appropriately

### Log Files
The system generates a `rov_control.log` log file during operation, containing detailed runtime information and error records.

## Development Guide

### Code Structure
```
QGC/
├── requirements.txt          # Dependency list
├── config.ini               # Configuration file
├── mavlink_interface.py     # MAVLink communication interface
├── auto_controller.py       # Automatic controller (with MPC)
├── virtual_joystick.py      # Virtual joystick
├── main_controller.py       # Main controller
├── example_usage.py         # Usage examples
└── README.md                # Documentation
```

### Extending Development
1. **Add New Control Algorithms**: Inherit AutoController class
2. **Integrate New Sensors**: Modify MavlinkInterface class
3. **Custom Control Interface**: Extend VirtualJoystick class
4. **Add New Safety Features**: Add to main controller

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contributing

Issues and Pull Requests are welcome to improve this project.

## Contact

If you have questions or suggestions, please contact us through:
- Submit GitHub Issues
- Email the project maintainers

---

**Note**: When using this system to control ROVs, please ensure you are in a safe environment and comply with relevant underwater operation regulations.