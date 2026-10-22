#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVLink通信接口模块
负责与ArduSub水下ROV的通信
"""

import time
import threading
from typing import Optional, Dict, Any
from pymavlink import mavutil
from pymavlink import mavwp
import configparser
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MavlinkInterface:
    """MAVLink通信接口类"""
    
    def __init__(self, config_file: str = 'config.ini'):
        """初始化MAVLink接口"""
        self.config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        self.config.read(config_file, encoding='utf-8')
        
        self.mavlink_connection = None
        self.vehicle_state = {}
        self.connection_thread = None
        self.is_connected = False
        self.connection_type = self.config.get('Connection', 'connection_type')
        
        # 初始化车辆状态
        self._init_vehicle_state()
        
    def _init_vehicle_state(self):
        """初始化车辆状态字典"""
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
        """建立MAVLink连接"""
        try:
            if self.connection_type == 'udp':
                host = self.config.get('Connection', 'udp_host')
                port = self.config.getint('Connection', 'udp_port')
                connection_string = f'udpin:{host}:{port}'
            else:
                port = self.config.get('Connection', 'serial_port')
                baud = self.config.getint('Connection', 'baud_rate')
                connection_string = f'{port}:{baud}'
            
            logger.info(f"正在连接到: {connection_string}")
            self.mavlink_connection = mavutil.mavlink_connection(connection_string)
            
            # 等待心跳
            self.mavlink_connection.wait_heartbeat(timeout=10)
            logger.info("MAVLink连接成功！")
            
            # 请求数据流
            try:
                target_system = self.mavlink_connection.target_system
                target_component = self.mavlink_connection.target_component
                logger.info(f"目标系统: {target_system}, 组件: {target_component}")
                
                # 请求所有数据流，频率10Hz
                self.mavlink_connection.mav.request_data_stream_send(
                    target_system, target_component,
                    mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
                )
                logger.info("已请求数据流")
            except Exception as e:
                logger.warning(f"数据流请求失败: {e}")
            
            # 启动状态监听线程
            self._start_state_listener()
            self.is_connected = True
            return True
            
        except Exception as e:
            logger.error(f"连接失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.mavlink_connection:
            self.mavlink_connection.close()
            self.is_connected = False
            logger.info("MAVLink连接已断开")
    
    def _start_state_listener(self):
        """启动状态监听线程"""
        self.connection_thread = threading.Thread(target=self._state_listener_loop, daemon=True)
        self.connection_thread.start()
    
    def _state_listener_loop(self):
        """状态监听循环"""
        while self.is_connected:
            try:
                # 非阻塞方式获取所有可用消息
                msg = self.mavlink_connection.recv_match(blocking=False, timeout=0.1)
                if msg is None:
                    time.sleep(0.1)
                    continue
                
                # 处理不同类型的消息
                if msg.get_type() == 'ATTITUDE':
                    self.vehicle_state['attitude'] = {
                        'roll': msg.roll,
                        'pitch': msg.pitch,
                        'yaw': msg.yaw
                    }
                    logger.info(f"姿态更新: roll={msg.roll:.2f}, pitch={msg.pitch:.2f}, yaw={msg.yaw:.2f}")
                
                elif msg.get_type() == 'GLOBAL_POSITION_INT':
                    self.vehicle_state['position'] = {
                        'lat': msg.lat / 1e7,
                        'lon': msg.lon / 1e7,
                        'alt': msg.alt / 1000.0,
                        'depth': -msg.alt / 1000.0  # 深度为负值
                    }
                    logger.info(f"位置更新: depth={-msg.alt/1000.0:.2f}m")
                
                elif msg.get_type() == 'SYS_STATUS':
                    self.vehicle_state['battery'] = {
                        'voltage': msg.voltage_battery / 1000.0,
                        'current': msg.current_battery / 100.0,
                        'remaining': msg.battery_remaining
                    }
                    logger.info(f"电池更新: {msg.battery_remaining}%")
                
                elif msg.get_type() == 'HEARTBEAT':
                    # 检查解锁状态 - 使用正确的位掩码
                    armed = bool(msg.base_mode & 0x80)
                    self.vehicle_state['armed'] = armed
                    
                    # 获取飞行模式
                    try:
                        mode = mavutil.mode_string_v10(msg)
                        self.vehicle_state['mode'] = mode
                    except:
                        self.vehicle_state['mode'] = 'UNKNOWN'
                    
                    # 获取系统状态
                    self.vehicle_state['system_status'] = msg.system_status
                    
                    logger.info(f"心跳更新: armed={armed}, mode={self.vehicle_state['mode']}, system_status={msg.system_status}")
                    
                    # 如果收到心跳，说明连接正常
                    if not hasattr(self, '_last_heartbeat_time'):
                        self._last_heartbeat_time = time.time()
                    self._last_heartbeat_time = time.time()
                
                elif msg.get_type() == 'VFR_HUD':
                    # 获取更多飞行信息
                    if hasattr(msg, 'alt'):
                        self.vehicle_state['position']['alt'] = msg.alt
                    if hasattr(msg, 'groundspeed'):
                        self.vehicle_state['velocity']['vx'] = msg.groundspeed
                    logger.info(f"VFR_HUD更新: alt={msg.alt:.1f}m, groundspeed={msg.groundspeed:.1f}m/s")
                
                elif msg.get_type() == 'SCALED_PRESSURE':
                    # 获取压力传感器数据（用于深度计算）
                    if hasattr(msg, 'press_abs'):
                        # 简单的深度计算（需要根据实际情况调整）
                        pressure = msg.press_abs
                        depth = (pressure - 101325) / (1025 * 9.81)  # 假设海水密度1025 kg/m³
                        self.vehicle_state['position']['depth'] = depth
                        logger.info(f"压力更新: {pressure:.1f} Pa, 深度: {depth:.2f}m")
                
                elif msg.get_type() == 'COMMAND_ACK':
                    logger.info(f"命令确认: {msg.command}, 结果: {msg.result}")
                
                elif msg.get_type() == 'RC_CHANNELS':
                    # 监听RC通道数据
                    logger.info(f"RC通道: 1={msg.chan1_raw}, 2={msg.chan2_raw}, 3={msg.chan3_raw}, 4={msg.chan4_raw}")
                
                elif msg.get_type() == 'SERVO_OUTPUT_RAW':
                    # 监听舵机输出
                    logger.info(f"舵机输出: 1={msg.servo1_raw}, 2={msg.servo2_raw}, 3={msg.servo3_raw}, 4={msg.servo4_raw}")
                
                elif msg.get_type() == 'RAW_IMU':
                    # 监听IMU原始数据
                    logger.info(f"IMU数据: acc={msg.xacc/1000:.2f}, {msg.yacc/1000:.2f}, {msg.zacc/1000:.2f}")
                
                else:
                    # 记录其他消息类型（降低频率）
                    if not hasattr(self, '_last_other_msg_time'):
                        self._last_other_msg_time = 0
                    if time.time() - self._last_other_msg_time > 5:  # 5秒显示一次
                        logger.info(f"收到消息: {msg.get_type()}")
                        self._last_other_msg_time = time.time()
                
            except Exception as e:
                logger.warning(f"状态监听错误: {e}")
                time.sleep(0.1)
    
    @staticmethod
    def _to_rc(value: float) -> int:
        """-1.0..1.0 -> 1000..2000"""
        value = max(-1.0, min(1.0, value))
        return int(round(1500 + value * 500))

    def send_manual_control(self, roll: float, pitch: float, throttle: float, yaw: float,
                            forward: float = 0.0, lateral: float = 0.0):
        """
        发送手动控制指令（RC_CHANNELS_OVERRIDE）。

        ArduSub 默认的 RC 输入通道映射：
          1 Pitch, 2 Roll, 3 Throttle(垂直), 4 Yaw, 5 Forward(前后), 6 Lateral(左右平移)
        所有输入范围 -1.0 ~ 1.0，1500 为中位。
        """
        if not self.is_connected:
            logger.warning("未连接，无法发送控制指令")
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
            logger.debug(f"发送RC控制: {channels}")
            return True
            
        except Exception as e:
            logger.error(f"发送控制指令失败: {e}")
            return False
    
    def send_rc_channels_override(self, channels: Dict[int, int]):
        """发送RC通道覆盖指令"""
        if not self.is_connected:
            logger.warning("未连接，无法发送RC覆盖指令")
            return False
        
        try:
            # 创建通道数组
            rc_channels = [65535] * 18  # 18个通道，65535表示不覆盖
            
            for channel_id, value in channels.items():
                if 1 <= channel_id <= 18:
                    rc_channels[channel_id - 1] = value
            
            # 发送RC_CHANNELS_OVERRIDE消息
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
            logger.error(f"发送RC覆盖指令失败: {e}")
            return False
    
    def get_vehicle_state(self) -> Dict[str, Any]:
        """获取当前车辆状态"""
        return self.vehicle_state.copy()
    
    def is_vehicle_armed(self) -> bool:
        """检查车辆是否已解锁"""
        return self.vehicle_state.get('armed', False)
    
    def get_depth(self) -> float:
        """获取当前深度"""
        return self.vehicle_state.get('position', {}).get('depth', 0.0)
    
    def get_heading(self) -> float:
        """获取当前航向"""
        yaw = self.vehicle_state.get('attitude', {}).get('yaw', 0.0)
        # 转换为0-360度
        heading = (yaw * 180 / 3.14159) % 360
        return heading
