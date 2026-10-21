#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用示例
展示如何使用ArduSub ROV自动控制系统
"""

import time
import logging
from main_controller import ROVMainController

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_manual_control():
    """手动控制示例"""
    logger.info("=== 手动控制示例 ===")
    
    # 创建控制器
    controller = ROVMainController()
    
    try:
        # 启动控制器
        controller.start()
        
        # 等待连接建立
        time.sleep(2)
        
        logger.info("手动控制模式已启动")
        logger.info("使用以下按键控制ROV:")
        logger.info("W/S - 俯仰控制")
        logger.info("A/D - 横滚控制")
        logger.info("Q/E - 偏航控制")
        logger.info("空格/Shift - 油门控制")
        logger.info("R - 重置控制")
        logger.info("ESC - 紧急停止")
        logger.info("M - 切换模式")
        
        # 运行一段时间
        time.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        controller.shutdown()

def example_auto_control():
    """自动控制示例"""
    logger.info("=== 自动控制示例 ===")
    
    # 创建控制器
    controller = ROVMainController()
    
    try:
        # 启动控制器
        controller.start()
        
        # 等待连接建立
        time.sleep(2)
        
        # 切换到自动模式
        controller.set_control_mode('auto')
        
        # 设置目标深度和航向
        controller.set_target_depth(-2.0)  # 目标深度2米
        controller.set_target_heading(90.0)  # 目标航向90度
        
        logger.info("自动控制模式已启动")
        logger.info(f"目标深度: -2.0m")
        logger.info(f"目标航向: 90.0°")
        
        # 运行一段时间
        time.sleep(60)
        
        # 更改目标
        controller.set_target_depth(-3.0)
        controller.set_target_heading(180.0)
        logger.info("目标已更新")
        logger.info(f"新目标深度: -3.0m")
        logger.info(f"新目标航向: 180.0°")
        
        # 继续运行
        time.sleep(30)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        controller.shutdown()

def example_custom_algorithm():
    """自定义算法示例"""
    logger.info("=== 自定义算法示例 ===")
    
    # 创建控制器
    controller = ROVMainController()
    
    try:
        # 启动控制器
        controller.start()
        
        # 等待连接建立
        time.sleep(2)
        
        logger.info("自定义算法模式已启动")
        logger.info("实现您自己的智能控制算法...")
        
        # 示例：简单的深度巡航算法
        depths = [-1.0, -2.0, -3.0, -2.0, -1.0]
        headings = [0.0, 45.0, 90.0, 135.0, 180.0]
        
        for i, (depth, heading) in enumerate(zip(depths, headings)):
            logger.info(f"执行第 {i+1} 个航点")
            logger.info(f"目标深度: {depth}m, 目标航向: {heading}°")
            
            # 切换到自动模式
            controller.set_control_mode('auto')
            
            # 设置目标
            controller.set_target_depth(depth)
            controller.set_target_heading(heading)
            
            # 等待到达目标
            time.sleep(20)
            
            # 短暂停留
            time.sleep(5)
        
        logger.info("巡航任务完成")
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        controller.shutdown()

def example_emergency_handling():
    """紧急情况处理示例"""
    logger.info("=== 紧急情况处理示例 ===")
    
    # 创建控制器
    controller = ROVMainController()
    
    try:
        # 启动控制器
        controller.start()
        
        # 等待连接建立
        time.sleep(2)
        
        logger.info("紧急情况处理示例已启动")
        logger.info("演示紧急停止功能...")
        
        # 运行一段时间
        time.sleep(5)
        
        # 模拟紧急情况
        logger.warning("检测到紧急情况，执行紧急停止！")
        controller.emergency_stop()
        
        # 等待紧急停止完成
        time.sleep(3)
        
        logger.info("紧急情况已处理，恢复正常控制")
        
        # 继续运行
        time.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        controller.shutdown()

def main():
    """主函数"""
    logger.info("ArduSub ROV自动控制系统 - 使用示例")
    logger.info("请选择要运行的示例:")
    logger.info("1. 手动控制示例")
    logger.info("2. 自动控制示例")
    logger.info("3. 自定义算法示例")
    logger.info("4. 紧急情况处理示例")
    logger.info("5. 退出")
    
    while True:
        try:
            choice = input("\n请输入选择 (1-5): ").strip()
            
            if choice == '1':
                example_manual_control()
            elif choice == '2':
                example_auto_control()
            elif choice == '3':
                example_custom_algorithm()
            elif choice == '4':
                example_emergency_handling()
            elif choice == '5':
                logger.info("退出程序")
                break
            else:
                logger.warning("无效选择，请输入1-5")
                
        except KeyboardInterrupt:
            logger.info("\n用户中断，退出程序")
            break
        except Exception as e:
            logger.error(f"示例运行错误: {e}")

if __name__ == "__main__":
    main()
