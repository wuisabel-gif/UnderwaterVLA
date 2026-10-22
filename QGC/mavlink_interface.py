#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVLink communication interface module
Handles communication with the ArduSub underwater ROV
"""

import time
import threading
from typing import Optional, Dict, Any
from pymavlink import mavutil
from pymavlink import mavwp
import configparser
import logging

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MavlinkInterface:
    """MAVLink communication interface"""

    def __init__(self, config_file: str = 'config.ini'):
        """Initialize the MAVLink interface"""
        self.config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        self.config.read(config_file, encoding='utf-8')

        self.mavlink_connection = None
        self.vehicle_state = {}
        self.connection_thread = None
        self.is_connected = False
        self.connection_type = self.config.get('Connection', 'connection_type')

        # Initialize the vehicle state
        self._init_vehicle_state()

    def _init_vehicle_state(self):
        """Initialize the vehicle state dict"""
        self.vehicle_state = {
            'attitude': {'roll': 0, 'pitch': 0, 'yaw': 0},
            'position': {'lat': 0, 'lon': 0, 'alt': 0, 'depth': 0},
            'velocity': {'vx': 0, 'vy': 0, 'vz': 0},
            'battery': {'voltage': 0, 'current': 0, 'remaining': 0},
            'mode': 'UNKNOWN',
            'armed': False,
            'system_status': 'UNKNOWN'
        }

    def connect(self) -> bool:
        """Establish the MAVLink connection"""
        try:
            if self.connection_type == 'udp':
                host = self.config.get('Connection', 'udp_host')
                port = self.config.getint('Connection', 'udp_port')
                connection_string = f'udpin:{host}:{port}'
            else:
                port = self.config.get('Connection', 'serial_port')
                baud = self.config.getint('Connection', 'baud_rate')
                connection_string = f'{port}:{baud}'

            logger.info(f"Connecting to: {connection_string}")
            self.mavlink_connection = mavutil.mavlink_connection(connection_string)

            # Wait for a heartbeat
            self.mavlink_connection.wait_heartbeat(timeout=10)
            logger.info("MAVLink connected!")

            # Request data streams
            try:
                target_system = self.mavlink_connection.target_system
                target_component = self.mavlink_connection.target_component
                logger.info(f"Target system: {target_system}, component: {target_component}")

                # Request all data streams at 10 Hz
                self.mavlink_connection.mav.request_data_stream_send(
                    target_system, target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
                )
                logger.info("Data streams requested")
            except Exception as e:
                logger.warning(f"Data stream request failed: {e}")

            # Start the state listener thread
            self._start_state_listener()
            self.is_connected = True
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.is_connected = False
            return False

    def disconnect(self):
        """Disconnect"""
        if self.mavlink_connection:
            self.mavlink_connection.close()
            self.is_connected = False
            logger.info("MAVLink disconnected")

    def _start_state_listener(self):
        """Start the state listener thread"""
        self.connection_thread = threading.Thread(target=self._state_listener_loop, daemon=True)
        self.connection_thread.start()

    def _state_listener_loop(self):
        """State listener loop"""
        while self.is_connected:
            try:
                # Non-blocking read of any available message
                msg = self.mavlink_connection.recv_match(blocking=False, timeout=0.1)
                if msg is None:
                    time.sleep(0.1)
                    continue

                # Handle each message type
                if msg.get_type() == 'ATTITUDE':
                    self.vehicle_state['attitude'] = {
                        'roll': msg.roll,
                        'pitch': msg.pitch,
                        'yaw': msg.yaw
                    }
                    logger.info(f"Attitude update: roll={msg.roll:.2f}, pitch={msg.pitch:.2f}, yaw={msg.yaw:.2f}")

                elif msg.get_type() == 'GLOBAL_POSITION_INT':
                    self.vehicle_state['position'] = {
                        'lat': msg.lat / 1e7,
                        'lon': msg.lon / 1e7,
                        'alt': msg.alt / 1000.0,
                        'depth': -msg.alt / 1000.0  # depth is negative
                    }
                    logger.info(f"Position update: depth={-msg.alt/1000.0:.2f}m")

                elif msg.get_type() == 'SYS_STATUS':
                    self.vehicle_state['battery'] = {
                        'voltage': msg.voltage_battery / 1000.0,
                        'current': msg.current_battery / 100.0,
                        'remaining': msg.battery_remaining
                    }
                    logger.info(f"Battery update: {msg.battery_remaining}%")

                elif msg.get_type() == 'HEARTBEAT':
                    # Check the armed state using the correct bit mask
                    armed = bool(msg.base_mode & 0x80)
                    self.vehicle_state['armed'] = armed

                    # Read the flight mode
                    try:
                        mode = mavutil.mode_string_v10(msg)
                        self.vehicle_state['mode'] = mode
                    except:
                        self.vehicle_state['mode'] = 'UNKNOWN'

                    # Read the system status
                    self.vehicle_state['system_status'] = msg.system_status

                    logger.info(f"Heartbeat update: armed={armed}, mode={self.vehicle_state['mode']}, system_status={msg.system_status}")

                    # A heartbeat means the link is healthy
                    if not hasattr(self, '_last_heartbeat_time'):
                        self._last_heartbeat_time = time.time()
                    self._last_heartbeat_time = time.time()

                elif msg.get_type() == 'VFR_HUD':
                    # Extra flight information
                    if hasattr(msg, 'alt'):
                        self.vehicle_state['position']['alt'] = msg.alt
                    if hasattr(msg, 'groundspeed'):
                        self.vehicle_state['velocity']['vx'] = msg.groundspeed
                    logger.info(f"VFR_HUD update: alt={msg.alt:.1f}m, groundspeed={msg.groundspeed:.1f}m/s")

                elif msg.get_type() == 'SCALED_PRESSURE':
                    # Pressure sensor data (used for depth)
                    if hasattr(msg, 'press_abs'):
                        # Simple depth calculation (adjust for the real setup)
                        pressure = msg.press_abs
                        depth = (pressure - 101325) / (1025 * 9.81)  # assumes seawater density 1025 kg/m³
                        self.vehicle_state['position']['depth'] = depth
                        logger.info(f"Pressure update: {pressure:.1f} Pa, depth: {depth:.2f}m")

                elif msg.get_type() == 'COMMAND_ACK':
                    logger.info(f"Command ack: {msg.command}, result: {msg.result}")

                elif msg.get_type() == 'RC_CHANNELS':
                    # RC channel data
                    logger.info(f"RC channels: 1={msg.chan1_raw}, 2={msg.chan2_raw}, 3={msg.chan3_raw}, 4={msg.chan4_raw}")

                elif msg.get_type() == 'SERVO_OUTPUT_RAW':
                    # Servo outputs
                    logger.info(f"Servo outputs: 1={msg.servo1_raw}, 2={msg.servo2_raw}, 3={msg.servo3_raw}, 4={msg.servo4_raw}")

                elif msg.get_type() == 'RAW_IMU':
                    # Raw IMU data
                    logger.info(f"IMU data: acc={msg.xacc/1000:.2f}, {msg.yacc/1000:.2f}, {msg.zacc/1000:.2f}")

                else:
                    # Log other message types (rate limited)
                    if not hasattr(self, '_last_other_msg_time'):
                        self._last_other_msg_time = 0
                    if time.time() - self._last_other_msg_time > 5:  # once every 5 seconds
                        logger.info(f"Received message: {msg.get_type()}")
                        self._last_other_msg_time = time.time()

            except Exception as e:
                logger.warning(f"State listener error: {e}")
                time.sleep(0.1)

    @staticmethod
    def _to_rc(value: float) -> int:
        """-1.0..1.0 -> 1000..2000"""
        value = max(-1.0, min(1.0, value))
        return int(round(1500 + value * 500))

    def send_manual_control(self, roll: float, pitch: float, throttle: float, yaw: float,
                            forward: float = 0.0, lateral: float = 0.0):
        """
        Send a manual control command (RC_CHANNELS_OVERRIDE).

        ArduSub's default RC input channel mapping:
          1 Pitch, 2 Roll, 3 Throttle (vertical), 4 Yaw, 5 Forward (fore/aft), 6 Lateral (strafe)
        All inputs range -1.0 ~ 1.0; 1500 is neutral.
        """
        if not self.is_connected:
            logger.warning("Not connected, cannot send control command")
            return False

        try:
            channels = {
                1: self._to_rc(pitch),
                2: self._to_rc(roll),
                3: self._to_rc(throttle),
                4: self._to_rc(yaw),
                5: self._to_rc(forward),
                6: self._to_rc(lateral),
            }
            self.mavlink_connection.mav.rc_channels_override_send(
                self.mavlink_connection.target_system,
                self.mavlink_connection.target_component,
                channels[1], channels[2], channels[3], channels[4],
                channels[5], channels[6], 65535, 65535
            )
            logger.debug(f"Sent RC control: {channels}")
            return True

        except Exception as e:
            logger.error(f"Failed to send control command: {e}")
            return False

    def send_rc_channels_override(self, channels: Dict[int, int]):
        """Send an RC channel override command"""
        if not self.is_connected:
            logger.warning("Not connected, cannot send RC override")
            return False

        try:
            # Build the channel array
            rc_channels = [65535] * 18  # 18 channels, 65535 means "do not override"

            for channel_id, value in channels.items():
                if 1 <= channel_id <= 18:
                    rc_channels[channel_id - 1] = value

            # Send the RC_CHANNELS_OVERRIDE message
            self.mavlink_connection.mav.rc_channels_override_send(
                target_system=self.mavlink_connection.target_system,
                target_component=self.mavlink_connection.target_component,
                chan1_raw=rc_channels[0],
                chan2_raw=rc_channels[1],
                chan3_raw=rc_channels[2],
                chan4_raw=rc_channels[3],
                chan5_raw=rc_channels[4],
                chan6_raw=rc_channels[5],
                chan7_raw=rc_channels[6],
                chan8_raw=rc_channels[7]
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send RC override: {e}")
            return False

    def get_vehicle_state(self) -> Dict[str, Any]:
        """Get the current vehicle state"""
        return self.vehicle_state.copy()

    def is_vehicle_armed(self) -> bool:
        """Check whether the vehicle is armed"""
        return self.vehicle_state.get('armed', False)

    def get_depth(self) -> float:
        """Get the current depth"""
        return self.vehicle_state.get('position', {}).get('depth', 0.0)

    def get_heading(self) -> float:
        """Get the current heading"""
        yaw = self.vehicle_state.get('attitude', {}).get('yaw', 0.0)
        # Convert to 0-360 degrees
        heading = (yaw * 180 / 3.14159) % 360
        return heading