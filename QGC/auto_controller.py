#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatic control module
Contains the PID controller, the automatic control logic and the MPC controller
"""

import time
import threading
import numpy as np
from typing import Dict, Any, Optional
import configparser
import logging

logger = logging.getLogger(__name__)

class PIDController:
    """PID controller"""

    def __init__(self, kp: float, ki: float, kd: float,
                 output_min: float = -1.0, output_max: float = 1.0):
        """Initialize the PID controller"""
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max

        # State variables
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()

    def reset(self):
        """Reset the controller state"""
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()

    def update(self, setpoint: float, current_value: float) -> float:
        """Update the PID controller and return the control output"""
        current_time = time.time()
        dt = current_time - self.last_time

        if dt <= 0:
            return 0.0

        # Error
        error = setpoint - current_value

        # Integral term
        self.integral += error * dt

        # Derivative term
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0

        # PID output
        output = self.kp * error + self.ki * self.integral + self.kd * derivative

        # Clamp the output
        output = max(self.output_min, min(self.output_max, output))

        # Update state
        self.prev_error = error
        self.last_time = current_time

        return output

class MPCController:
    """Model predictive controller"""

    def __init__(self, config: configparser.ConfigParser):
        """Initialize the MPC controller"""
        # MPC parameters
        self.control_horizon = 1.0  # 1 s control horizon
        self.control_interval = 0.02  # 20 ms control interval
        self.steps = int(self.control_horizon / self.control_interval)

        # Speed map (low / medium / high)
        self.speed_map = {
            'low': {'translational': 0.2, 'rotational': 0.5},
            'medium': {'translational': 0.5, 'rotational': 1.0},
            'high': {'translational': 0.8, 'rotational': 1.5}
        }

        # Weights
        self.beta = config.getfloat('MPC', 'beta', fallback=1.0)  # tracking error weight
        self.gamma = config.getfloat('MPC', 'gamma', fallback=0.1)  # control effort weight
        self.delta = config.getfloat('MPC', 'delta', fallback=0.05)  # hydrodynamic drag weight

        # System parameters
        self.mass = config.getfloat('MPC', 'mass', fallback=10.0)  # vehicle mass (kg)
        self.inertia = config.getfloat('MPC', 'inertia', fallback=0.5)  # moment of inertia (kg·m²)
        self.translational_drag_coeff = config.getfloat('MPC', 'translational_drag_coeff', fallback=5.0)  # translational drag coefficient
        self.rotational_drag_coeff = config.getfloat('MPC', 'rotational_drag_coeff', fallback=0.1)  # rotational drag coefficient

        # Current state
        self.current_velocity = 0.0
        self.current_angular_rate = 0.0
        self.estimated_translational_drag = 0.0
        self.estimated_rotational_drag = 0.0

        # Control mode
        self.motion_axis = 'forward'  # forward / lateral / throttle / yaw
        self.target_velocity = 0.0
        self.target_angular_rate = 0.0
        self.reference_profile = []

        # Control status
        self.is_active = False
        self.start_time = 0.0

    # direction -> (output axis, sign). Axis names match AutoController.control_outputs / MavlinkInterface:
    # forward=fore/aft (ch5) lateral=strafe left/right (ch6) throttle=up/down (ch3) yaw=turn in place (ch4)
    DIRECTION_AXES = {
        'forward': ('forward', 1), 'backward': ('forward', -1),
        'right': ('lateral', 1), 'left': ('lateral', -1),
        'up': ('throttle', 1), 'down': ('throttle', -1),
        'turn_right': ('yaw', 1), 'turn_left': ('yaw', -1),
        'stop': ('forward', 0),
    }

    def set_vla_command(self, direction: str, speed: str):
        """Set the VLA command and generate the reference trajectory"""
        if direction not in self.DIRECTION_AXES:
            logger.warning(f"Unknown direction command: {direction}")
            self.is_active = False
            return
        self.is_active = True
        self.start_time = time.time()
        self.motion_axis, sign = self.DIRECTION_AXES[direction]
        if self.motion_axis == 'yaw':
            r_cmd = sign * self.speed_map.get(speed, {}).get('rotational', 0.0)
            self.target_angular_rate = r_cmd
            self.reference_profile = self._generate_rotational_profile(r_cmd)
        else:
            v_cmd = sign * self.speed_map.get(speed, {}).get('translational', 0.0)
            self.target_velocity = v_cmd
            self.reference_profile = self._generate_translational_profile(v_cmd)

    def _generate_translational_profile(self, v_cmd: float) -> list:
        """Generate the translational reference trajectory"""
        profile = []
        for i in range(self.steps):
            t = i * self.control_interval
            if 0 <= t < 0.2:
                v_ref = v_cmd * min(5 * t, 1)
            elif 0.2 <= t < 0.5:
                v_ref = v_cmd
            elif 0.5 <= t <= 1:
                v_ref = v_cmd * max(1 - 2 * (t - 0.5), 0)
            else:
                v_ref = 0.0
            profile.append(v_ref)
        return profile

    def _generate_rotational_profile(self, r_cmd: float) -> list:
        """Generate the rotational reference trajectory"""
        profile = []
        for i in range(self.steps):
            t = i * self.control_interval
            if 0 <= t < 0.2:
                r_ref = r_cmd * min(5 * t, 1)
            elif 0.2 <= t < 0.5:
                r_ref = r_cmd
            elif 0.5 <= t <= 1:
                r_ref = r_cmd * max(1 - 2 * (t - 0.5), 0)
            else:
                r_ref = 0.0
            profile.append(r_ref)
        return profile

    def update_state(self, vehicle_state: Dict[str, Any]):
        """Update the vehicle state"""
        # Update current velocity and angular rate
        if 'velocity' in vehicle_state:
            velocity = vehicle_state['velocity']
            # Assume the x-axis velocity is the translational velocity
            self.current_velocity = velocity.get('x', 0.0)

        if 'attitude' in vehicle_state:
            attitude = vehicle_state['attitude']
            # Use the yaw rate
            self.current_angular_rate = attitude.get('yaw_rate', 0.0)

    ZERO = {'forward': 0.0, 'lateral': 0.0, 'throttle': 0.0, 'yaw': 0.0}

    def compute_control(self) -> Dict[str, float]:
        """Compute the MPC control output: four axes, only the axis of the current action is non-zero"""
        out = dict(self.ZERO)
        if not self.is_active:
            return out
        elapsed_time = time.time() - self.start_time
        if elapsed_time > self.control_horizon:
            self.is_active = False
            return out
        step = min(int(elapsed_time / self.control_interval), len(self.reference_profile) - 1)
        reference_value = self.reference_profile[step]
        self._estimate_drag()
        if self.motion_axis == 'yaw':
            out['yaw'] = self._compute_rotational_control(reference_value)
        else:
            # ponytail: all three translational axes share the forward velocity feedback; lateral/vertical degrade to open loop without their own velocity measurement
            out[self.motion_axis] = self._compute_translational_control(reference_value)
        return out

    def _estimate_drag(self):
        """Estimate hydrodynamic drag"""
        try:
            # Translational drag estimate
            if abs(self.current_velocity) > 0.01:  # avoid division by zero
                # D_v = (τ_v - M*v_dot) / (v*|v|)
                # Simplified: compute from the current velocity and the drag coefficient
                self.estimated_translational_drag = self.translational_drag_coeff * self.current_velocity * abs(self.current_velocity)

            # Rotational drag estimate
            if abs(self.current_angular_rate) > 0.01:  # avoid division by zero
                # D_r = (τ_r - I_z*r_dot) / (r*|r|)
                # Simplified: compute from the current angular rate and the drag coefficient
                self.estimated_rotational_drag = self.rotational_drag_coeff * self.current_angular_rate * abs(self.current_angular_rate)
        except Exception as e:
            logger.warning(f"Drag estimation error: {e}")

    def _compute_translational_control(self, reference_velocity: float) -> float:
        """Compute the translational control output"""
        # Tracking error
        velocity_error = reference_velocity - self.current_velocity

        # MPC objective
        # Simplified: proportional control plus drag compensation
        thrust = (self.beta * velocity_error +
                 self.delta * self.estimated_translational_drag) / self.mass

        # Clamp the output
        thrust = max(-1.0, min(1.0, thrust))
        return thrust

    def _compute_rotational_control(self, reference_angular_rate: float) -> float:
        """Compute the rotational control output"""
        # Tracking error
        angular_rate_error = reference_angular_rate - self.current_angular_rate

        # MPC objective
        # Simplified: proportional control plus drag compensation
        yaw_rate = (self.beta * angular_rate_error +
                   self.delta * self.estimated_rotational_drag) / self.inertia

        # Clamp the output
        yaw_rate = max(-1.0, min(1.0, yaw_rate))
        return yaw_rate

class AutoController:
    """Automatic controller"""

    def __init__(self, config_file: str = 'config.ini'):
        """Initialize the automatic controller"""
        self.config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        self.config.read(config_file, encoding='utf-8')

        # Control parameters
        self.control_frequency = self.config.getint('Control', 'control_frequency')
        self.max_throttle = self.config.getint('Control', 'max_throttle') / 100.0
        self.max_yaw_rate = self.config.getfloat('Control', 'max_yaw_rate')
        self.max_pitch_angle = self.config.getfloat('Control', 'max_pitch_angle')
        self.max_roll_angle = self.config.getfloat('Control', 'max_roll_angle')

        # Automatic control parameters
        self.enable_depth_hold = self.config.getboolean('AutoControl', 'enable_depth_hold')
        self.target_depth = self.config.getfloat('AutoControl', 'target_depth')
        self.depth_tolerance = self.config.getfloat('AutoControl', 'depth_tolerance')
        self.enable_heading_hold = self.config.getboolean('AutoControl', 'enable_heading_hold')
        self.target_heading = self.config.getfloat('AutoControl', 'target_heading')
        self.heading_tolerance = self.config.getfloat('AutoControl', 'heading_tolerance')

        # Safety parameters
        self.emergency_stop_timeout = self.config.getfloat('Safety', 'emergency_stop_timeout')
        self.max_depth = self.config.getfloat('Safety', 'max_depth')
        self.min_depth = self.config.getfloat('Safety', 'min_depth')

        # Initialize controllers
        self._init_controllers()

        # Control status
        self.is_active = False
        self.control_thread = None
        self.last_control_time = 0
        self.emergency_stop_time = 0

        # Control outputs
        # roll/pitch/yaw: attitude; throttle: vertical (up/down); forward: fore/aft; lateral: strafe left/right
        self.control_outputs = self._zero_outputs()

    @staticmethod
    def _zero_outputs() -> Dict[str, float]:
        return {'roll': 0.0, 'pitch': 0.0, 'throttle': 0.0, 'yaw': 0.0, 'forward': 0.0, 'lateral': 0.0}

    def _init_controllers(self):
        """Initialize the controllers"""
        # PID controllers
        self._init_pid_controllers()

        # MPC controller
        self.mpc_controller = MPCController(self.config)

    def _init_pid_controllers(self):
        """Initialize the PID controllers"""
        # Depth-hold PID (pitch control)
        self.depth_pid = PIDController(
            kp=0.5,    # proportional gain
            ki=0.1,    # integral gain
            kd=0.2,    # derivative gain
            output_min=-0.5,
            output_max=0.5
        )

        # Heading-hold PID (yaw control)
        self.heading_pid = PIDController(
            kp=0.8,    # proportional gain
            ki=0.05,   # integral gain
            kd=0.3,    # derivative gain
            output_min=-0.8,
            output_max=0.8
        )

        # Roll stabilization PID
        self.roll_pid = PIDController(
            kp=1.0,    # proportional gain
            ki=0.0,    # integral gain
            kd=0.5,    # derivative gain
            output_min=-0.3,
            output_max=0.3
        )

    def start(self):
        """Start automatic control"""
        if self.is_active:
            logger.warning("Automatic control is already running")
            return

        self.is_active = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        logger.info("Automatic control started")

    def stop(self):
        """Stop automatic control"""
        self.is_active = False
        if self.control_thread:
            self.control_thread.join(timeout=1.0)

        # Reset all controllers
        self.depth_pid.reset()
        self.heading_pid.reset()
        self.roll_pid.reset()
        self.mpc_controller.is_active = False

        # Zero the control outputs
        self.control_outputs = self._zero_outputs()

        logger.info("Automatic control stopped")

    def _control_loop(self):
        """Main control loop"""
        while self.is_active:
            try:
                current_time = time.time()

                # Rate limit
                if current_time - self.last_control_time < 1.0 / self.control_frequency:
                    time.sleep(0.01)
                    continue

                # Run the automatic control logic
                self._execute_auto_control()

                self.last_control_time = current_time

            except Exception as e:
                logger.error(f"Control loop error: {e}")
                time.sleep(0.1)

    def _execute_auto_control(self):
        """Run the automatic control logic"""
        # Current vehicle state, provided externally
        # These values are updated through update_vehicle_state
        current_depth = getattr(self, '_current_depth', 0.0)
        current_heading = getattr(self, '_current_heading', 0.0)
        current_roll = getattr(self, '_current_roll', 0.0)

        # Depth hold
        if self.enable_depth_hold:
            depth_error = abs(self.target_depth - current_depth)
            if depth_error > self.depth_tolerance:
                # The ROV holds depth with the vertical thrusters (throttle channel), not pitch
                self.control_outputs['throttle'] = self.depth_pid.update(self.target_depth, current_depth)
            else:
                self.control_outputs['throttle'] = 0.0

        # Heading hold
        if self.enable_heading_hold:
            heading_error = abs(self.target_heading - current_heading)
            if heading_error > self.heading_tolerance:
                yaw_output = self.heading_pid.update(self.target_heading, current_heading)
                self.control_outputs['yaw'] = yaw_output
            else:
                self.control_outputs['yaw'] = 0.0

        # Roll stabilization
        roll_output = self.roll_pid.update(0.0, current_roll)
        self.control_outputs['roll'] = roll_output

        # MPC control
        if self.mpc_controller.is_active:
            mpc_outputs = self.mpc_controller.compute_control()
            self.control_outputs['forward'] = mpc_outputs['forward']
            self.control_outputs['lateral'] = mpc_outputs['lateral']
            if self.mpc_controller.motion_axis == 'throttle':
                self.control_outputs['throttle'] = mpc_outputs['throttle']  # overrides depth hold
            self.control_outputs['yaw'] += mpc_outputs['yaw']  # added on top of heading hold
            for k in ('forward', 'lateral', 'throttle', 'yaw'):
                self.control_outputs[k] = max(-1.0, min(1.0, self.control_outputs[k]))

        # Safety check
        self._safety_check()

    def _safety_check(self):
        """Safety check"""
        current_time = time.time()

        # Depth limit check. Depth is negative: deeper is more negative.
        # Only exceeding the max depth triggers an emergency stop; being shallower than min_depth
        # (including 0 m at the surface) only logs, otherwise the ROV would be emergency-stopped
        # over and over at the surface and could never dive.
        current_depth = getattr(self, '_current_depth', 0.0)
        if current_depth < self.max_depth:
            logger.warning(f"Depth exceeds the maximum limit: {current_depth}m < {self.max_depth}m")
            self._emergency_stop()
            return
        if current_depth > self.min_depth:
            logger.debug(f"Depth is shallower than the minimum limit: {current_depth}m > {self.min_depth}m")

        # Emergency stop timeout check
        if self.emergency_stop_time > 0 and current_time - self.emergency_stop_time > self.emergency_stop_timeout:
            logger.warning("Emergency stop timed out, resuming normal control")
            self.emergency_stop_time = 0

    def _emergency_stop(self):
        """Emergency stop"""
        logger.warning("Executing emergency stop!")
        self.emergency_stop_time = time.time()

        # Zero all control outputs
        self.control_outputs = self._zero_outputs()

        # Reset controllers
        self.depth_pid.reset()
        self.heading_pid.reset()
        self.roll_pid.reset()
        self.mpc_controller.is_active = False

    def set_target_depth(self, depth: float):
        """Set the target depth"""
        if self.min_depth <= depth <= self.max_depth:
            self.target_depth = depth
            logger.info(f"Target depth set to: {depth}m")
        else:
            logger.warning(f"Target depth {depth}m is outside the safe range")

    def set_target_heading(self, heading: float):
        """Set the target heading"""
        # Normalize heading to 0-360 degrees
        heading = heading % 360
        self.target_heading = heading
        logger.info(f"Target heading set to: {heading}°")

    def execute_vla_command(self, direction: str, speed: str):
        """Execute a VLA command"""
        logger.info(f"Executing VLA command: direction={direction}, speed={speed}")
        self.mpc_controller.set_vla_command(direction, speed)

    def update_vehicle_state(self, vehicle_state: Dict[str, Any]):
        """Update the vehicle state (called externally)"""
        # Update current state values
        if 'position' in vehicle_state and 'depth' in vehicle_state['position']:
            self._current_depth = vehicle_state['position']['depth']

        if 'attitude' in vehicle_state and 'yaw' in vehicle_state['attitude']:
            yaw = vehicle_state['attitude']['yaw']
            # Convert to 0-360 degrees
            self._current_heading = (yaw * 180 / 3.14159) % 360

        if 'attitude' in vehicle_state and 'roll' in vehicle_state['attitude']:
            self._current_roll = vehicle_state['attitude']['roll']

        # Update the MPC controller state
        self.mpc_controller.update_state(vehicle_state)

    def get_control_outputs(self) -> Dict[str, float]:
        """Get the current control outputs"""
        return self.control_outputs.copy()
