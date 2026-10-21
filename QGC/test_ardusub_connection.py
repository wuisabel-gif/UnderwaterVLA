#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ArduSub连接测试
用于测试与ArduSub ROV的MAVLink通信
"""

import time
import logging
from mavlink_interface import MavlinkInterface

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mavlink_connection():
    """测试MAVLink连接"""
    logger.info("=== ArduSub MAVLink连接测试 ===")
    
    # 创建MAVLink接口
    mavlink_interface = MavlinkInterface('config.ini')
    
    try:
        # 尝试连接
        logger.info("正在连接ArduSub...")
        if mavlink_interface.connect():
            logger.info("✅ MAVLink连接成功！")
            
            # 等待一段时间获取状态
            logger.info("等待获取ROV状态...")
            time.sleep(3)
            
            # 获取并显示ROV状态
            vehicle_state = mavlink_interface.get_vehicle_state()
            logger.info("ROV状态信息:")
            logger.info(f"  连接状态: {'已连接' if mavlink_interface.is_connected else '未连接'}")
            logger.info(f"  解锁状态: {'已解锁' if mavlink_interface.is_vehicle_armed() else '未解锁'}")
            logger.info(f"  飞行模式: {vehicle_state.get('mode', '未知')}")
            logger.info(f"  当前深度: {vehicle_state.get('position', {}).get('depth', 0.0):.2f}m")
            logger.info(f"  当前航向: {mavlink_interface.get_heading():.1f}°")
            logger.info(f"  电池电量: {vehicle_state.get('battery', {}).get('remaining', 0)}%")
            logger.info(f"  电池电压: {vehicle_state.get('battery', {}).get('voltage', 0.0):.2f}V")
            
            # 测试发送控制指令
            logger.info("\n测试发送控制指令...")
            logger.info("发送停止指令 (roll=0, pitch=0, throttle=0, yaw=0)")
            
            if mavlink_interface.send_manual_control(0.0, 0.0, 0.0, 0.0):
                logger.info("✅ 控制指令发送成功")
            else:
                logger.error("❌ 控制指令发送失败")
            
            # 持续监控状态
            logger.info("\n开始持续监控ROV状态 (按Ctrl+C停止)...")
            try:
                while True:
                    vehicle_state = mavlink_interface.get_vehicle_state()
                    depth = vehicle_state.get('position', {}).get('depth', 0.0)
                    heading = mavlink_interface.get_heading()
                    battery = vehicle_state.get('battery', {}).get('remaining', 0)
                    
                    print(f"\r深度: {depth:6.2f}m | 航向: {heading:6.1f}° | 电池: {battery:3d}%", end='')
                    time.sleep(1.0)
                    
            except KeyboardInterrupt:
                logger.info("\n\n用户中断监控")
                
        else:
            logger.error("❌ MAVLink连接失败")
            logger.error("请检查以下项目:")
            logger.error("1. QGroundControl是否正在运行")
            logger.error("2. ArduSub ROV是否已连接")
            logger.error("3. 配置文件中的连接参数是否正确")
            logger.error("4. 防火墙是否阻止了UDP连接")
            
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        
    finally:
        # 断开连接
        mavlink_interface.disconnect()
        logger.info("MAVLink连接已断开")

def test_control_commands():
    """测试控制指令"""
    logger.info("\n=== 控制指令测试 ===")
    
    mavlink_interface = MavlinkInterface('config.ini')
    
    try:
        if not mavlink_interface.connect():
            logger.error("无法连接，跳过控制测试")
            return
            
        logger.info("连接成功，开始控制测试...")
        
        # 测试各种控制指令
        test_commands = [
            ("停止", 0.0, 0.0, 0.0, 0.0),
            ("前进", 0.0, 0.3, 0.0, 0.0),
            ("后退", 0.0, -0.3, 0.0, 0.0),
            ("左转", 0.0, 0.0, 0.0, -0.3),
            ("右转", 0.0, 0.0, 0.0, 0.3),
            ("上升", 0.0, 0.0, 0.3, 0.0),
            ("下降", 0.0, 0.0, -0.3, 0.0),
            ("停止", 0.0, 0.0, 0.0, 0.0),
        ]
        
        for name, roll, pitch, throttle, yaw in test_commands:
            logger.info(f"执行: {name} (roll={roll}, pitch={pitch}, throttle={throttle}, yaw={yaw})")
            
            if mavlink_interface.send_manual_control(roll, pitch, throttle, yaw):
                logger.info("✅ 指令发送成功")
            else:
                logger.error("❌ 指令发送失败")
            
            # 等待指令执行
            time.sleep(2.0)
            
        logger.info("控制测试完成")
        
    except Exception as e:
        logger.error(f"控制测试错误: {e}")
        
    finally:
        mavlink_interface.disconnect()

def main():
    """主函数"""
    logger.info("ArduSub ROV连接测试程序")
    logger.info("请确保:")
    logger.info("1. QGroundControl正在运行")
    logger.info("2. ArduSub ROV已连接并解锁")
    logger.info("3. 配置文件config.ini设置正确")
    
    input("\n按Enter键开始测试...")
    
    # 测试连接
    test_mavlink_connection()
    
    # 询问是否测试控制指令
    try:
        choice = input("\n是否测试控制指令? (y/n): ").strip().lower()
        if choice == 'y':
            test_control_commands()
    except KeyboardInterrupt:
        pass
    
    logger.info("测试完成")

if __name__ == "__main__":
    main()
