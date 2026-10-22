#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Virtual joystick module
Simulates joystick input from the keyboard and mouse
"""

import time
import threading
import pygame
import keyboard
from typing import Dict, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)

class VirtualJoystick:
    """Virtual joystick"""

    def __init__(self):
        """Initialize the virtual joystick"""
        # Initialize Pygame
        pygame.init()

        # Joystick state
        self.joystick_state = {
            'roll': 0.0,      # roll (-1.0 to 1.0)
            'pitch': 0.0,     # pitch (-1.0 to 1.0)
            'throttle': 0.0,  # throttle (-1.0 to 1.0)
            'yaw': 0.0,       # yaw (-1.0 to 1.0)
            'buttons': {}      # button state
        }

        # Control parameters
        self.control_sensitivity = 0.1  # control sensitivity
        self.return_to_center = True    # auto-center the sticks
        self.return_speed = 0.05        # centering speed

        # Control status
        self.is_active = False
        self.control_thread = None

        # Callback
        self.control_callback = None

        # Key mapping
        self.key_mapping = {
            'w': 'pitch_forward',      # W - pitch forward
            's': 'pitch_backward',     # S - pitch backward
            'a': 'roll_left',          # A - roll left
            'd': 'roll_right',         # D - roll right
            'q': 'yaw_left',           # Q - yaw left
            'e': 'yaw_right',          # E - yaw right
            'space': 'throttle_up',    # Space - throttle up
            'shift': 'throttle_down',  # Shift - throttle down
            'r': 'reset_controls',     # R - reset controls
            'esc': 'emergency_stop'    # ESC - emergency stop
        }

        # Register keyboard listeners
        self._setup_keyboard_listeners()

    def _setup_keyboard_listeners(self):
        """Register the keyboard listeners"""
        for key, action in self.key_mapping.items():
            if key == 'shift':
                keyboard.on_press_key('shift', lambda e: self._handle_key_action(action))
                keyboard.on_release_key('shift', lambda e: self._handle_key_release(action))
            elif key == 'space':
                keyboard.on_press_key('space', lambda e: self._handle_key_action(action))
                keyboard.on_release_key('space', lambda e: self._handle_key_release(action))
            else:
                keyboard.on_press_key(key, lambda e, a=action: self._handle_key_action(a))
                keyboard.on_release_key(key, lambda e, a=action: self._handle_key_release(a))

    def _handle_key_action(self, action: str):
        """Handle a key press"""
        if action == 'pitch_forward':
            self.joystick_state['pitch'] = min(1.0, self.joystick_state['pitch'] + self.control_sensitivity)
        elif action == 'pitch_backward':
            self.joystick_state['pitch'] = max(-1.0, self.joystick_state['pitch'] - self.control_sensitivity)
        elif action == 'roll_left':
            self.joystick_state['roll'] = max(-1.0, self.joystick_state['roll'] - self.control_sensitivity)
        elif action == 'roll_right':
            self.joystick_state['roll'] = min(1.0, self.joystick_state['roll'] + self.control_sensitivity)
        elif action == 'yaw_left':
            self.joystick_state['yaw'] = max(-1.0, self.joystick_state['yaw'] - self.control_sensitivity)
        elif action == 'yaw_right':
            self.joystick_state['yaw'] = min(1.0, self.joystick_state['yaw'] + self.control_sensitivity)
        elif action == 'throttle_up':
            self.joystick_state['throttle'] = min(1.0, self.joystick_state['throttle'] + self.control_sensitivity)
        elif action == 'throttle_down':
            self.joystick_state['throttle'] = max(-1.0, self.joystick_state['throttle'] - self.control_sensitivity)
        elif action == 'reset_controls':
            self._reset_controls()
        elif action == 'emergency_stop':
            self._emergency_stop()

    def _handle_key_release(self, action: str):
        """Handle a key release"""
        # Logic for keys that must be held down can go here
        pass

    def _reset_controls(self):
        """Reset all controls"""
        self.joystick_state['roll'] = 0.0
        self.joystick_state['pitch'] = 0.0
        self.joystick_state['throttle'] = 0.0
        self.joystick_state['yaw'] = 0.0
        logger.info("Controls reset")

    def _emergency_stop(self):
        """Emergency stop"""
        self._reset_controls()
        logger.warning("Emergency stop executed!")

    def start(self):
        """Start the virtual joystick"""
        if self.is_active:
            logger.warning("Virtual joystick is already running")
            return

        self.is_active = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        logger.info("Virtual joystick started")
        logger.info("Controls:")
        logger.info("W/S - pitch")
        logger.info("A/D - roll")
        logger.info("Q/E - yaw")
        logger.info("Space/Shift - throttle")
        logger.info("R - reset controls")
        logger.info("ESC - emergency stop")

    def stop(self):
        """Stop the virtual joystick"""
        self.is_active = False
        if self.control_thread:
            self.control_thread.join(timeout=1.0)

        # Reset controls
        self._reset_controls()
        logger.info("Virtual joystick stopped")

    def _control_loop(self):
        """Main control loop"""
        while self.is_active:
            try:
                # Auto-centering
                if self.return_to_center:
                    self._auto_return_to_center()

                # Invoke the callback
                if self.control_callback:
                    self.control_callback(self.joystick_state)

                time.sleep(0.02)  # 50 Hz update rate

            except Exception as e:
                logger.error(f"Control loop error: {e}")
                time.sleep(0.1)

    def _auto_return_to_center(self):
        """Auto-center the sticks"""
        for axis in ['roll', 'pitch', 'yaw']:
            if abs(self.joystick_state[axis]) > 0.01:
                if self.joystick_state[axis] > 0:
                    self.joystick_state[axis] = max(0, self.joystick_state[axis] - self.return_speed)
                else:
                    self.joystick_state[axis] = min(0, self.joystick_state[axis] + self.return_speed)
            else:
                self.joystick_state[axis] = 0.0

    def set_control_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set the control callback"""
        self.control_callback = callback

    def get_joystick_state(self) -> Dict[str, Any]:
        """Get the current joystick state"""
        return self.joystick_state.copy()

    def set_control_sensitivity(self, sensitivity: float):
        """Set the control sensitivity"""
        self.control_sensitivity = max(0.01, min(1.0, sensitivity))
        logger.info(f"Control sensitivity set to: {self.control_sensitivity}")

    def set_return_to_center(self, enabled: bool):
        """Enable or disable auto-centering"""
        self.return_to_center = enabled
        logger.info(f"Auto-centering: {'enabled' if enabled else 'disabled'}")

    def set_return_speed(self, speed: float):
        """Set the centering speed"""
        self.return_speed = max(0.01, min(0.5, speed))
        logger.info(f"Centering speed set to: {self.return_speed}")

    def set_manual_control(self, roll: float, pitch: float, throttle: float, yaw: float):
        """Set the control values directly"""
        self.joystick_state['roll'] = max(-1.0, min(1.0, roll))
        self.joystick_state['pitch'] = max(-1.0, min(1.0, pitch))
        self.joystick_state['throttle'] = max(-1.0, min(1.0, throttle))
        self.joystick_state['yaw'] = max(-1.0, min(1.0, yaw))

    def cleanup(self):
        """Clean up resources"""
        self.stop()
        pygame.quit()
