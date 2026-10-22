#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main controller
Ties all modules together and exposes a single control interface
"""

import time
import threading
import signal
import sys
from typing import Dict, Any, Optional
import logging
import json

from mavlink_interface import MavlinkInterface
from auto_controller import AutoController
from virtual_joystick import VirtualJoystick

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('rov_control.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ROVMainController:
    """ROV main controller"""

    def __init__(self, config_file: str = 'config.ini'):
        """Initialize the main controller"""
        self.config_file = config_file

        # Initialize the modules
        self.mavlink_interface = MavlinkInterface(config_file)
        self.auto_controller = AutoController(config_file)
        self.virtual_joystick = VirtualJoystick()

        # Control status
        self.is_running = False
        self.control_mode = 'manual'  # 'manual' or 'auto'
        self.control_thread = None

        # VLA command queue
        self.vla_command_queue = []
        self.vla_command_lock = threading.Lock()

        # Register the virtual joystick callback
        self.virtual_joystick.set_control_callback(self._joystick_callback)

        # Signal handling
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("ROV main controller initialized")

    def _signal_handler(self, signum, frame):
        """Signal handler"""
        logger.info(f"Received signal {signum}, shutting down...")
        self.shutdown()
        sys.exit(0)

    def start(self):
        """Start the main controller"""
        if self.is_running:
            logger.warning("Main controller is already running")
            return

        try:
            # Connect MAVLink
            logger.info("Connecting MAVLink...")
            if not self.mavlink_interface.connect():
                logger.error("MAVLink connection failed, cannot start")
                return

            # Start the virtual joystick
            logger.info("Starting virtual joystick...")
            self.virtual_joystick.start()

            # Start the control thread
            self.is_running = True
            self.control_thread = threading.Thread(target=self._main_control_loop, daemon=True)
            self.control_thread.start()

            logger.info("ROV main controller started!")
            logger.info("Control mode: manual")
            logger.info("Press 'M' to toggle manual/auto mode")
            logger.info("Press 'ESC' for emergency stop")
            logger.info("Press 'Ctrl+C' to exit")

        except Exception as e:
            logger.error(f"Startup failed: {e}")
            self.shutdown()

    def shutdown(self):
        """Shut down the main controller"""
        logger.info("Shutting down ROV main controller...")

        self.is_running = False

        # Stop automatic control
        if self.auto_controller.is_active:
            self.auto_controller.stop()

        # Stop the virtual joystick
        if self.virtual_joystick.is_active:
            self.virtual_joystick.stop()

        # Disconnect MAVLink
        if self.mavlink_interface.is_connected:
            self.mavlink_interface.disconnect()

        # Wait for the thread to finish
        if self.control_thread:
            self.control_thread.join(timeout=2.0)

        # Clean up resources
        self.virtual_joystick.cleanup()

        logger.info("ROV main controller shut down")

    def _main_control_loop(self):
        """Main control loop"""
        while self.is_running:
            try:
                # Check the connection
                if not self.mavlink_interface.is_connected:
                    logger.warning("MAVLink connection lost, reconnecting...")
                    if self.mavlink_interface.connect():
                        logger.info("MAVLink reconnected")
                    else:
                        time.sleep(5.0)
                        continue

                # Run the logic for the current control mode
                if self.control_mode == 'manual':
                    self._manual_control_loop()
                elif self.control_mode == 'auto':
                    self._auto_control_loop()

                time.sleep(0.02)  # 50 Hz update rate

            except Exception as e:
                logger.error(f"Main control loop error: {e}")
                time.sleep(0.1)

    def _manual_control_loop(self):
        """Manual control loop"""
        # Read the virtual joystick state
        joystick_state = self.virtual_joystick.get_joystick_state()

        # Send the control command to the ROV
        self.mavlink_interface.send_manual_control(
            roll=joystick_state['roll'],
            pitch=joystick_state['pitch'],
            throttle=joystick_state['throttle'],
            yaw=joystick_state['yaw']
        )

    def _auto_control_loop(self):
        """Automatic control loop"""
        # Read the current vehicle state
        vehicle_state = self.mavlink_interface.get_vehicle_state()

        # Push the vehicle state into the automatic controller
        self.auto_controller.update_vehicle_state(vehicle_state)

        # Process the VLA command queue
        self._process_vla_commands()

        # Read the automatic control outputs
        control_outputs = self.auto_controller.get_control_outputs()

        # Send the control command to the ROV
        self.mavlink_interface.send_manual_control(
            roll=control_outputs['roll'],
            pitch=control_outputs['pitch'],
            throttle=control_outputs['throttle'],
            yaw=control_outputs['yaw'],
            forward=control_outputs.get('forward', 0.0),
            lateral=control_outputs.get('lateral', 0.0)
        )

    def _process_vla_commands(self):
        """Process the VLA command queue"""
        with self.vla_command_lock:
            if self.vla_command_queue:
                # Take the first command in the queue
                vla_command = self.vla_command_queue.pop(0)

                # Execute the VLA command
                direction = vla_command.get('direction')
                speed = vla_command.get('speed')

                if direction and speed:
                    self.auto_controller.execute_vla_command(direction, speed)

    def _joystick_callback(self, joystick_state: Dict[str, Any]):
        """Virtual joystick callback"""
        # Check for special keys
        if 'm' in joystick_state.get('buttons', {}):
            self._toggle_control_mode()

    def _toggle_control_mode(self):
        """Toggle the control mode"""
        if self.control_mode == 'manual':
            self.control_mode = 'auto'
            self.auto_controller.start()
            logger.info("Switched to automatic control mode")
        else:
            self.control_mode = 'manual'
            self.auto_controller.stop()
            logger.info("Switched to manual control mode")

    def set_control_mode(self, mode: str):
        """Set the control mode"""
        if mode not in ['manual', 'auto']:
            logger.warning(f"Invalid control mode: {mode}")
            return

        if mode != self.control_mode:
            if mode == 'auto':
                self.auto_controller.start()
            else:
                self.auto_controller.stop()

            self.control_mode = mode
            logger.info(f"Control mode set to: {mode}")

    def set_target_depth(self, depth: float):
        """Set the target depth"""
        if self.control_mode == 'auto':
            self.auto_controller.set_target_depth(depth)
        else:
            logger.warning("Cannot set target depth in manual mode")

    def set_target_heading(self, heading: float):
        """Set the target heading"""
        if self.control_mode == 'auto':
            self.auto_controller.set_target_heading(heading)
        else:
            logger.warning("Cannot set target heading in manual mode")

    def execute_vla_command(self, json_input):
        """
        Execute a VLA command
        :param json_input: JSON string or dict containing direction and speed
        """
        # Parse a string input into a dict
        if isinstance(json_input, str):
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON input: {e}")
                return
        elif isinstance(json_input, dict):
            data = json_input
        else:
            logger.error("Input must be a JSON string or a dict")
            return

        # Extract the action
        action = data.get('action', {})
        direction = action.get('direction')
        speed = action.get('speed')

        # Validate the parameters
        if not direction or not speed:
            logger.error("VLA command is missing direction or speed")
            return

        # Add the command to the queue
        with self.vla_command_lock:
            self.vla_command_queue.append({
                'direction': direction,
                'speed': speed
            })

        logger.info(f"VLA command queued: direction={direction}, speed={speed}")

    def get_status(self) -> Dict[str, Any]:
        """Get the system status"""
        return {
            'is_running': self.is_running,
            'control_mode': self.control_mode,
            'mavlink_connected': self.mavlink_interface.is_connected,
            'auto_controller_active': self.auto_controller.is_active,
            'virtual_joystick_active': self.virtual_joystick.is_active,
            'vehicle_state': self.mavlink_interface.get_vehicle_state(),
            'control_outputs': self.auto_controller.get_control_outputs() if self.control_mode == 'auto' else {}
        }

    def emergency_stop(self):
        """Emergency stop"""
        logger.warning("Executing emergency stop!")

        # Stop automatic control
        if self.auto_controller.is_active:
            self.auto_controller.stop()

        # Reset the virtual joystick
        self.virtual_joystick._reset_controls()

        # Send a stop command
        self.mavlink_interface.send_manual_control(0.0, 0.0, 0.0, 0.0)

        # Clear the VLA command queue
        with self.vla_command_lock:
            self.vla_command_queue.clear()

        logger.info("Emergency stop complete")

def main():
    """Entry point"""
    try:
        # Create the main controller
        controller = ROVMainController()

        # Start the controller
        controller.start()

        # Main loop
        while controller.is_running:
            try:
                time.sleep(1.0)

                # Show status
                status = controller.get_status()
                if status['mavlink_connected']:
                    vehicle_state = status['vehicle_state']
                    depth = vehicle_state.get('position', {}).get('depth', 0.0)
                    heading = vehicle_state.get('attitude', {}).get('yaw', 0.0) * 180 / 3.14159
                    battery = vehicle_state.get('battery', {}).get('remaining', 0)

                    print(f"\rStatus: {status['control_mode']} | Depth: {depth:.2f}m | Heading: {heading:.1f}° | Battery: {battery}%", end='')

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                time.sleep(1.0)

    except Exception as e:
        logger.error(f"Program error: {e}")
    finally:
        # Shut down the controller
        if 'controller' in locals():
            controller.shutdown()

if __name__ == "__main__":
    main()