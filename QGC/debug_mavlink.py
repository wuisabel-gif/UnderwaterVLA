#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MAVLink消息调试工具
监控所有接收到的MAVLink消息
"""

import time
import logging
from pymavlink import mavutil

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def debug_mavlink_messages():
    """调试MAVLink消息"""
    logger.info("=== MAVLink消息调试工具 ===")
    logger.info("正在连接到QGroundControl...")
    
    try:
        # 连接到QGC
        connection = mavutil.mavlink_connection('udpin:127.0.0.1:14550')
        
        # 等待心跳
        logger.info("等待MAVLink心跳...")
        connection.wait_heartbeat(timeout=10)
        logger.info("✅ 连接成功！")
        
        # 设置目标系统
        target_system = connection.target_system
        target_component = connection.target_component
        logger.info(f"目标系统: {target_system}, 组件: {target_component}")
        
        # 请求数据流
        logger.info("请求数据流...")
        connection.mav.request_data_stream_send(
            target_system, target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1
        )
        
        # 监控所有消息
        logger.info("开始监控MAVLink消息 (按Ctrl+C停止)...")
        message_count = {}
        
        try:
            while True:
                msg = connection.recv_match(blocking=True, timeout=1.0)
                if msg is not None:
                    msg_type = msg.get_type()
                    message_count[msg_type] = message_count.get(msg_type, 0) + 1
                    
                    # 显示消息内容
                    logger.info(f"收到消息: {msg_type}")
                    
                    # 根据消息类型显示详细信息
                    if msg_type == 'HEARTBEAT':
                        logger.info(f"  系统ID: {msg.get_srcSystem()}, 组件ID: {msg.get_srcComponent()}")
                        logger.info(f"  类型: {msg.type}, 自动导航: {msg.autopilot}, 基础模式: {msg.base_mode}")
                        logger.info(f"  自定义模式: {msg.custom_mode}, 系统状态: {msg.system_status}")
                        
                        # 检查解锁状态
                        armed = bool(msg.base_mode & 0x80)
                        logger.info(f"  解锁状态: {'已解锁' if armed else '未解锁'}")
                        
                        # 获取飞行模式
                        try:
                            mode = mavutil.mode_string_v10(msg)
                            logger.info(f"  飞行模式: {mode}")
                        except:
                            logger.info(f"  飞行模式: 无法解析")
                    
                    elif msg_type == 'ATTITUDE':
                        logger.info(f"  时间戳: {msg.time_boot_ms}ms")
                        logger.info(f"  姿态: roll={msg.roll:.3f}, pitch={msg.pitch:.3f}, yaw={msg.yaw:.3f}")
                        logger.info(f"  角速度: roll_rate={msg.rollspeed:.3f}, pitch_rate={msg.pitchspeed:.3f}, yaw_rate={msg.yawspeed:.3f}")
                    
                    elif msg_type == 'GLOBAL_POSITION_INT':
                        logger.info(f"  时间戳: {msg.time_boot_ms}ms")
                        logger.info(f"  位置: lat={msg.lat/1e7:.6f}°, lon={msg.lon/1e7:.6f}°")
                        logger.info(f"  高度: alt={msg.alt/1000.0:.2f}m, 相对高度: {msg.relative_alt/1000.0:.2f}m")
                        logger.info(f"  速度: vx={msg.vx/100.0:.2f}m/s, vy={msg.vy/100.0:.2f}m/s, vz={msg.vz/100.0:.2f}m/s")
                        logger.info(f"  航向: {msg.hdg/100.0:.1f}°")
                    
                    elif msg_type == 'SYS_STATUS':
                        logger.info(f"  时间戳: {msg.time_boot_ms}ms")
                        logger.info(f"  电压: {msg.voltage_battery/1000.0:.2f}V")
                        logger.info(f"  电流: {msg.current_battery/100.0:.2f}A")
                        logger.info(f"  电池剩余: {msg.battery_remaining}%")
                        logger.info(f"  通信丢失: {msg.drop_rate_comm}%")
                    
                    elif msg_type == 'VFR_HUD':
                        logger.info(f"  空速: {msg.airspeed:.1f}m/s")
                        logger.info(f"  地速: {msg.groundspeed:.1f}m/s")
                        logger.info(f"  高度: {msg.alt:.1f}m")
                        logger.info(f"  爬升率: {msg.climb:.1f}m/s")
                        logger.info(f"  航向: {msg.heading:.1f}°")
                        logger.info(f"  油门: {msg.throttle}%")
                    
                    elif msg_type == 'SCALED_PRESSURE':
                        logger.info(f"  时间戳: {msg.time_boot_ms}ms")
                        logger.info(f"  绝对压力: {msg.press_abs:.1f} Pa")
                        logger.info(f"  相对压力: {msg.press_diff:.1f} Pa")
                        logger.info(f"  温度: {msg.temperature/100.0:.1f}°C")
                    
                    elif msg_type == 'COMMAND_ACK':
                        logger.info(f"  命令: {msg.command}, 结果: {msg.result}")
                    
                    else:
                        # 显示其他消息的基本信息
                        logger.info(f"  消息ID: {msg.get_msgId()}")
                        logger.info(f"  源系统: {msg.get_srcSystem()}, 源组件: {msg.get_srcComponent()}")
                        
                        # 尝试显示消息属性
                        try:
                            for attr in dir(msg):
                                if not attr.startswith('_') and not callable(getattr(msg, attr)):
                                    value = getattr(msg, attr)
                                    if not isinstance(value, (int, float, str, bool)) or len(str(value)) < 100:
                                        logger.info(f"  {attr}: {value}")
                        except:
                            pass
                    
                    logger.info("")  # 空行分隔
                    
        except KeyboardInterrupt:
            logger.info("\n用户中断监控")
        
        # 显示统计信息
        logger.info("=== 消息统计 ===")
        for msg_type, count in sorted(message_count.items()):
            logger.info(f"{msg_type}: {count} 条")
        
    except Exception as e:
        logger.error(f"连接失败: {e}")
        return False
    
    finally:
        if 'connection' in locals():
            connection.close()
            logger.info("连接已断开")
    
    return True

def main():
    """主函数"""
    logger.info("MAVLink消息调试工具")
    logger.info("请确保:")
    logger.info("1. QGroundControl正在运行")
    logger.info("2. QGC中启用了UDP连接")
    logger.info("3. ArduSub ROV已连接")
    
    input("\n按Enter键开始调试...")
    
    # 开始调试
    debug_mavlink_messages()
    
    logger.info("调试完成")

if __name__ == "__main__":
    main()
