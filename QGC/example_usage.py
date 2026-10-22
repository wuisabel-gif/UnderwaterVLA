#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Usage examples
Show how to use the ArduSub ROV automatic control system
"""

import time
import logging
from main_controller import ROVMainController

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_manual_control():
    """Manual control example"""
    logger.info("=== Manual control example ===")

    # Create the controller
    controller = ROVMainController()

    try:
        # Start the controller
        controller.start()

        # Wait for the connection
        time.sleep(2)

        logger.info("Manual control mode started")
        logger.info("Use these keys to control the ROV:")
        logger.info("W/S - pitch")
        logger.info("A/D - roll")
        logger.info("Q/E - yaw")
        logger.info("Space/Shift - throttle")
        logger.info("R - reset controls")
        logger.info("ESC - emergency stop")
        logger.info("M - toggle mode")

        # Run for a while
        time.sleep(30)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        controller.shutdown()

def example_auto_control():
    """Automatic control example"""
    logger.info("=== Automatic control example ===")

    # Create the controller
    controller = ROVMainController()

    try:
        # Start the controller
        controller.start()

        # Wait for the connection
        time.sleep(2)

        # Switch to automatic mode
        controller.set_control_mode('auto')

        # Set the target depth and heading
        controller.set_target_depth(-2.0)  # target depth 2 m
        controller.set_target_heading(90.0)  # target heading 90 degrees

        logger.info("Automatic control mode started")
        logger.info(f"Target depth: -2.0m")
        logger.info(f"Target heading: 90.0°")

        # Run for a while
        time.sleep(60)

        # Change the targets
        controller.set_target_depth(-3.0)
        controller.set_target_heading(180.0)
        logger.info("Targets updated")
        logger.info(f"New target depth: -3.0m")
        logger.info(f"New target heading: 180.0°")

        # Keep running
        time.sleep(30)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        controller.shutdown()

def example_custom_algorithm():
    """Custom algorithm example"""
    logger.info("=== Custom algorithm example ===")

    # Create the controller
    controller = ROVMainController()

    try:
        # Start the controller
        controller.start()

        # Wait for the connection
        time.sleep(2)

        logger.info("Custom algorithm mode started")
        logger.info("Implement your own intelligent control algorithm here...")

        # Example: simple depth cruise
        depths = [-1.0, -2.0, -3.0, -2.0, -1.0]
        headings = [0.0, 45.0, 90.0, 135.0, 180.0]

        for i, (depth, heading) in enumerate(zip(depths, headings)):
            logger.info(f"Executing waypoint {i+1}")
            logger.info(f"Target depth: {depth}m, target heading: {heading}°")

            # Switch to automatic mode
            controller.set_control_mode('auto')

            # Set the targets
            controller.set_target_depth(depth)
            controller.set_target_heading(heading)

            # Wait to reach the target
            time.sleep(20)

            # Brief hold
            time.sleep(5)

        logger.info("Cruise mission complete")

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        controller.shutdown()

def example_emergency_handling():
    """Emergency handling example"""
    logger.info("=== Emergency handling example ===")

    # Create the controller
    controller = ROVMainController()

    try:
        # Start the controller
        controller.start()

        # Wait for the connection
        time.sleep(2)

        logger.info("Emergency handling example started")
        logger.info("Demonstrating the emergency stop...")

        # Run for a while
        time.sleep(5)

        # Simulate an emergency
        logger.warning("Emergency detected, executing emergency stop!")
        controller.emergency_stop()

        # Wait for the emergency stop to complete
        time.sleep(3)

        logger.info("Emergency handled, resuming normal control")

        # Keep running
        time.sleep(10)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        controller.shutdown()

def main():
    """Entry point"""
    logger.info("ArduSub ROV automatic control system - usage examples")
    logger.info("Choose an example to run:")
    logger.info("1. Manual control example")
    logger.info("2. Automatic control example")
    logger.info("3. Custom algorithm example")
    logger.info("4. Emergency handling example")
    logger.info("5. Exit")

    while True:
        try:
            choice = input("\nEnter your choice (1-5): ").strip()

            if choice == '1':
                example_manual_control()
            elif choice == '2':
                example_auto_control()
            elif choice == '3':
                example_custom_algorithm()
            elif choice == '4':
                example_emergency_handling()
            elif choice == '5':
                logger.info("Exiting")
                break
            else:
                logger.warning("Invalid choice, enter 1-5")

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user, exiting")
            break
        except Exception as e:
            logger.error(f"Example error: {e}")

if __name__ == "__main__":
    main()
