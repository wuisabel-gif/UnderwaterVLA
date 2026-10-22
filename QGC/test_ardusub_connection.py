#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArduSub connection test
Tests MAVLink communication with the ArduSub ROV
"""

import time
import logging
from mavlink_interface import MavlinkInterface

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mavlink_connection():
    """Test the MAVLink connection"""
    logger.info("=== ArduSub MAVLink connection test ===")

    # Create the MAVLink interface
    mavlink_interface = MavlinkInterface('config.ini')

    try:
        # Try to connect
        logger.info("Connecting to ArduSub...")
        if mavlink_interface.connect():
            logger.info("✅ MAVLink connected!")

            # Give it a moment to gather state
            logger.info("Waiting for ROV state...")
            time.sleep(3)

            # Read and show the ROV state
            vehicle_state = mavlink_interface.get_vehicle_state()
            logger.info("ROV state:")
            logger.info(f"  Connection: {'connected' if mavlink_interface.is_connected else 'disconnected'}")
            logger.info(f"  Armed: {'armed' if mavlink_interface.is_vehicle_armed() else 'disarmed'}")
            logger.info(f"  Flight mode: {vehicle_state.get('mode', 'unknown')}")
            logger.info(f"  Current depth: {vehicle_state.get('position', {}).get('depth', 0.0):.2f}m")
            logger.info(f"  Current heading: {mavlink_interface.get_heading():.1f}°")
            logger.info(f"  Battery level: {vehicle_state.get('battery', {}).get('remaining', 0)}%")
            logger.info(f"  Battery voltage: {vehicle_state.get('battery', {}).get('voltage', 0.0):.2f}V")

            # Test sending a control command
            logger.info("\nTesting control command send...")
            logger.info("Sending stop command (roll=0, pitch=0, throttle=0, yaw=0)")

            if mavlink_interface.send_manual_control(0.0, 0.0, 0.0, 0.0):
                logger.info("✅ Control command sent")
            else:
                logger.error("❌ Control command send failed")

            # Continuous state monitoring
            logger.info("\nMonitoring ROV state (press Ctrl+C to stop)...")
            try:
                while True:
                    vehicle_state = mavlink_interface.get_vehicle_state()
                    depth = vehicle_state.get('position', {}).get('depth', 0.0)
                    heading = mavlink_interface.get_heading()
                    battery = vehicle_state.get('battery', {}).get('remaining', 0)

                    print(f"\rDepth: {depth:6.2f}m | Heading: {heading:6.1f}° | Battery: {battery:3d}%", end='')
                    time.sleep(1.0)

            except KeyboardInterrupt:
                logger.info("\n\nMonitoring interrupted by user")

        else:
            logger.error("❌ MAVLink connection failed")
            logger.error("Check the following:")
            logger.error("1. Is QGroundControl running")
            logger.error("2. Is the ArduSub ROV connected")
            logger.error("3. Are the connection parameters in the config file correct")
            logger.error("4. Is a firewall blocking the UDP link")

    except Exception as e:
        logger.error(f"Error during test: {e}")

    finally:
        # Disconnect
        mavlink_interface.disconnect()
        logger.info("MAVLink disconnected")

def test_control_commands():
    """Test control commands"""
    logger.info("\n=== Control command test ===")

    mavlink_interface = MavlinkInterface('config.ini')

    try:
        if not mavlink_interface.connect():
            logger.error("Unable to connect, skipping control test")
            return

        logger.info("Connected, starting control test...")

        # Try each control command
        test_commands = [
            ("stop", 0.0, 0.0, 0.0, 0.0),
            ("forward", 0.0, 0.3, 0.0, 0.0),
            ("backward", 0.0, -0.3, 0.0, 0.0),
            ("turn left", 0.0, 0.0, 0.0, -0.3),
            ("turn right", 0.0, 0.0, 0.0, 0.3),
            ("ascend", 0.0, 0.0, 0.3, 0.0),
            ("descend", 0.0, 0.0, -0.3, 0.0),
            ("stop", 0.0, 0.0, 0.0, 0.0),
        ]

        for name, roll, pitch, throttle, yaw in test_commands:
            logger.info(f"Executing: {name} (roll={roll}, pitch={pitch}, throttle={throttle}, yaw={yaw})")

            if mavlink_interface.send_manual_control(roll, pitch, throttle, yaw):
                logger.info("✅ Command sent")
            else:
                logger.error("❌ Command send failed")

            # Wait for the command to take effect
            time.sleep(2.0)

        logger.info("Control test complete")

    except Exception as e:
        logger.error(f"Control test error: {e}")

    finally:
        mavlink_interface.disconnect()

def main():
    """Entry point"""
    logger.info("ArduSub ROV connection test")
    logger.info("Make sure that:")
    logger.info("1. QGroundControl is running")
    logger.info("2. The ArduSub ROV is connected and armed")
    logger.info("3. config.ini is set up correctly")

    input("\nPress Enter to start the test...")

    # Test the connection
    test_mavlink_connection()

    # Ask whether to test control commands
    try:
        choice = input("\nTest control commands? (y/n): ").strip().lower()
        if choice == 'y':
            test_control_commands()
    except KeyboardInterrupt:
        pass

    logger.info("Test complete")

if __name__ == "__main__":
    main()
