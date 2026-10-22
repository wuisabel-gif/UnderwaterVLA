#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVLink message debugging tool
Monitors every MAVLink message received
"""

import time
import logging
from pymavlink import mavutil

# Logging setup
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_mavlink_messages():
    """Debug MAVLink messages"""
    logger.info("=== MAVLink message debugging tool ===")
    logger.info("Connecting to QGroundControl...")

    try:
        # Connect to QGC
        connection = mavutil.mavlink_connection('udpin:127.0.0.1:14550')

        # Wait for a heartbeat
        logger.info("Waiting for MAVLink heartbeat...")
        connection.wait_heartbeat(timeout=10)
        logger.info("✅ Connected!")

        # Target system
        target_system = connection.target_system
        target_component = connection.target_component
        logger.info(f"Target system: {target_system}, component: {target_component}")

        # Request data streams
        logger.info("Requesting data streams...")
        connection.mav.request_data_stream_send(
            target_system, target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
        )

        # Monitor all messages
        logger.info("Monitoring MAVLink messages (press Ctrl+C to stop)...")
        message_count = {}

        try:
            while True:
                msg = connection.recv_match(blocking=True, timeout=1.0)
                if msg is not None:
                    msg_type = msg.get_type()
                    message_count[msg_type] = message_count.get(msg_type, 0) + 1

                    # Show the message
                    logger.info(f"Received message: {msg_type}")

                    # Show details per message type
                    if msg_type == 'HEARTBEAT':
                        logger.info(f"  System ID: {msg.get_srcSystem()}, component ID: {msg.get_srcComponent()}")
                        logger.info(f"  Type: {msg.type}, autopilot: {msg.autopilot}, base mode: {msg.base_mode}")
                        logger.info(f"  Custom mode: {msg.custom_mode}, system status: {msg.system_status}")

                        # Check the armed state
                        armed = bool(msg.base_mode & 0x80)
                        logger.info(f"  Armed: {'armed' if armed else 'disarmed'}")

                        # Read the flight mode
                        try:
                            mode = mavutil.mode_string_v10(msg)
                            logger.info(f"  Flight mode: {mode}")
                        except:
                            logger.info(f"  Flight mode: unable to parse")

                    elif msg_type == 'ATTITUDE':
                        logger.info(f"  Timestamp: {msg.time_boot_ms}ms")
                        logger.info(f"  Attitude: roll={msg.roll:.3f}, pitch={msg.pitch:.3f}, yaw={msg.yaw:.3f}")
                        logger.info(f"  Angular rates: roll_rate={msg.rollspeed:.3f}, pitch_rate={msg.pitchspeed:.3f}, yaw_rate={msg.yawspeed:.3f}")

                    elif msg_type == 'GLOBAL_POSITION_INT':
                        logger.info(f"  Timestamp: {msg.time_boot_ms}ms")
                        logger.info(f"  Position: lat={msg.lat/1e7:.6f}°, lon={msg.lon/1e7:.6f}°")
                        logger.info(f"  Altitude: alt={msg.alt/1000.0:.2f}m, relative altitude: {msg.relative_alt/1000.0:.2f}m")
                        logger.info(f"  Velocity: vx={msg.vx/100.0:.2f}m/s, vy={msg.vy/100.0:.2f}m/s, vz={msg.vz/100.0:.2f}m/s")
                        logger.info(f"  Heading: {msg.hdg/100.0:.1f}°")

                    elif msg_type == 'SYS_STATUS':
                        logger.info(f"  Timestamp: {msg.time_boot_ms}ms")
                        logger.info(f"  Voltage: {msg.voltage_battery/1000.0:.2f}V")
                        logger.info(f"  Current: {msg.current_battery/100.0:.2f}A")
                        logger.info(f"  Battery remaining: {msg.battery_remaining}%")
                        logger.info(f"  Comm drop rate: {msg.drop_rate_comm}%")

                    elif msg_type == 'VFR_HUD':
                        logger.info(f"  Airspeed: {msg.airspeed:.1f}m/s")
                        logger.info(f"  Groundspeed: {msg.groundspeed:.1f}m/s")
                        logger.info(f"  Altitude: {msg.alt:.1f}m")
                        logger.info(f"  Climb rate: {msg.climb:.1f}m/s")
                        logger.info(f"  Heading: {msg.heading:.1f}°")
                        logger.info(f"  Throttle: {msg.throttle}%")

                    elif msg_type == 'SCALED_PRESSURE':
                        logger.info(f"  Timestamp: {msg.time_boot_ms}ms")
                        logger.info(f"  Absolute pressure: {msg.press_abs:.1f} Pa")
                        logger.info(f"  Differential pressure: {msg.press_diff:.1f} Pa")
                        logger.info(f"  Temperature: {msg.temperature/100.0:.1f}°C")

                    elif msg_type == 'COMMAND_ACK':
                        logger.info(f"  Command: {msg.command}, result: {msg.result}")

                    else:
                        # Basic info for other messages
                        logger.info(f"  Message ID: {msg.get_msgId()}")
                        logger.info(f"  Source system: {msg.get_srcSystem()}, source component: {msg.get_srcComponent()}")

                        # Try to dump the message attributes
                        try:
                            for attr in dir(msg):
                                if not attr.startswith('_') and not callable(getattr(msg, attr)):
                                    value = getattr(msg, attr)
                                    if not isinstance(value, (int, float, str, bool)) or len(str(value)) < 100:
                                        logger.info(f"  {attr}: {value}")
                        except:
                            pass

                    logger.info("")  # blank line separator

        except KeyboardInterrupt:
            logger.info("\nMonitoring interrupted by user")

        # Show statistics
        logger.info("=== Message statistics ===")
        for msg_type, count in sorted(message_count.items()):
            logger.info(f"{msg_type}: {count}")

    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False

    finally:
        if 'connection' in locals():
            connection.close()
            logger.info("Disconnected")

    return True

def main():
    """Entry point"""
    logger.info("MAVLink message debugging tool")
    logger.info("Make sure that:")
    logger.info("1. QGroundControl is running")
    logger.info("2. The UDP link is enabled in QGC")
    logger.info("3. The ArduSub ROV is connected")

    input("\nPress Enter to start debugging...")

    # Start debugging
    debug_mavlink_messages()

    logger.info("Debugging finished")

if __name__ == "__main__":
    main()
