#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主控制器
整合所有模块，提供统一的控制接口
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

# 配置日志
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
    """ROV主控制器类"""
    
    def __init__(self, config_file: str = 'config.ini'):
        """初始化主控制器"""
        self.config_file = config_file
        
        # 初始化各个模块
        self.mavlink_interface = MavlinkInterface(config_file)
        self.auto_controller = AutoController(config_file)
        self.virtual_joystick = VirtualJoystick()
        
        # 控制状态
        self.is_running = False
        self.control_mode = 'manual'  # 'manual' 或 'auto'
        self.control_thread = None
        
        # VLA命令队列
        self.vla_command_queue = []
        self.vla_command_lock = threading.Lock()
        
        # 设置虚拟手柄回调
        self.virtual_joystick.set_control_callback(self._joystick_callback)
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("ROV主控制器初始化完成")
    
    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        logger.info(f"收到信号 {signum}，正在关闭...")
        self.shutdown()
        sys.exit(0)
    
    def start(self):
        """启动主控制器"""
        if self.is_running:
            logger.warning("主控制器已经在运行")
            return
        
        try:
            # 连接MAVLink
            logger.info("正在连接MAVLink...")
            if not self.mavlink_interface.connect():
                logger.error("MAVLink连接失败，无法启动")
                return
            
            # 启动虚拟手柄
            logger.info("启动虚拟手柄...")
            self.virtual_joystick.start()
            
            # 启动控制线程
            self.is_running = True
            self.control_thread = threading.Thread(target=self._main_control_loop, daemon=True)
            self.control_thread.start()
            
            logger.info("ROV主控制器启动成功！")
            logger.info("控制模式: 手动控制")
            logger.info("按 'M' 键切换手动/自动模式")
            logger.info("按 'ESC' 键紧急停止")
            logger.info("按 'Ctrl+C' 退出程序")
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            self.shutdown()
    
    def shutdown(self):
        """关闭主控制器"""
        logger.info("正在关闭ROV主控制器...")
        
        self.is_running = False
        
        # 停止自动控制
        if self.auto_controller.is_active:
            self.auto_controller.stop()
        
        # 停止虚拟手柄
        if self.virtual_joystick.is_active:
            self.virtual_joystick.stop()
        
        # 断开MAVLink连接
        if self.mavlink_interface.is_connected:
            self.mavlink_interface.disconnect()
        
        # 等待线程结束
        if self.control_thread:
            self.control_thread.join(timeout=2.0)
        
        # 清理资源
        self.virtual_joystick.cleanup()
        
        logger.info("ROV主控制器已关闭")
    
    def _main_control_loop(self):
        """主控制循环"""
        while self.is_running:
            try:
                # 检查连接状态
                if not self.mavlink_interface.is_connected:
                    logger.warning("MAVLink连接丢失，尝试重连...")
                    if self.mavlink_interface.connect():
                        logger.info("MAVLink重连成功")
                    else:
                        time.sleep(5.0)
                        continue
                
                # 根据控制模式执行相应逻辑
                if self.control_mode == 'manual':
                    self._manual_control_loop()
                elif self.control_mode == 'auto':
                    self._auto_control_loop()
                
                time.sleep(0.02)  # 50Hz更新频率
                
            except Exception as e:
                logger.error(f"主控制循环错误: {e}")
                time.sleep(0.1)
    
    def _manual_control_loop(self):
        """手动控制循环"""
        # 获取虚拟手柄状态
        joystick_state = self.virtual_joystick.get_joystick_state()
        
        # 发送控制指令到ROV
        self.mavlink_interface.send_manual_control(
            roll=joystick_state['roll'],
            pitch=joystick_state['pitch'],
            throttle=joystick_state['throttle'],
            yaw=joystick_state['yaw']
        )
    
    def _auto_control_loop(self):
        """自动控制循环"""
        # 获取当前车辆状态
        vehicle_state = self.mavlink_interface.get_vehicle_state()
        
        # 更新自动控制器的车辆状态
        self.auto_controller.update_vehicle_state(vehicle_state)
        
        # 处理VLA命令队列
        self._process_vla_commands()
        
        # 获取自动控制输出
        control_outputs = self.auto_controller.get_control_outputs()
        
        # 发送控制指令到ROV
        self.mavlink_interface.send_manual_control(
            roll=control_outputs['roll'],
            pitch=control_outputs['pitch'],
            throttle=control_outputs['throttle'],
            yaw=control_outputs['yaw']
        )
    
    def _process_vla_commands(self):
        """处理VLA命令队列"""
        with self.vla_command_lock:
            if self.vla_command_queue:
                # 获取队列中的第一个命令
                vla_command = self.vla_command_queue.pop(0)
                
                # 执行VLA命令
                direction = vla_command.get('direction')
                speed = vla_command.get('speed')
                
                if direction and speed:
                    self.auto_controller.execute_vla_command(direction, speed)
    
    def _joystick_callback(self, joystick_state: Dict[str, Any]):
        """虚拟手柄回调函数"""
        # 检查特殊按键
        if 'm' in joystick_state.get('buttons', {}):
            self._toggle_control_mode()
    
    def _toggle_control_mode(self):
        """切换控制模式"""
        if self.control_mode == 'manual':
            self.control_mode = 'auto'
            self.auto_controller.start()
            logger.info("切换到自动控制模式")
        else:
            self.control_mode = 'manual'
            self.auto_controller.stop()
            logger.info("切换到手动控制模式")
    
    def set_control_mode(self, mode: str):
        """设置控制模式"""
        if mode not in ['manual', 'auto']:
            logger.warning(f"无效的控制模式: {mode}")
            return
        
        if mode != self.control_mode:
            if mode == 'auto':
                self.auto_controller.start()
            else:
                self.auto_controller.stop()
            
            self.control_mode = mode
            logger.info(f"控制模式设置为: {mode}")
    
    def set_target_depth(self, depth: float):
        """设置目标深度"""
        if self.control_mode == 'auto':
            self.auto_controller.set_target_depth(depth)
        else:
            logger.warning("手动模式下无法设置目标深度")
    
    def set_target_heading(self, heading: float):
        """设置目标航向"""
        if self.control_mode == 'auto':
            self.auto_controller.set_target_heading(heading)
        else:
            logger.warning("手动模式下无法设置目标航向")
    
    def execute_vla_command(self, json_input):
        """
        执行VLA命令
        :param json_input: 包含方向和速度信息的JSON字符串或字典
        """
        # 如果输入是字符串，则解析为字典
        if isinstance(json_input, str):
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                logger.error(f"无效的JSON输入: {e}")
                return
        elif isinstance(json_input, dict):
            data = json_input
        else:
            logger.error("输入必须是JSON字符串或字典")
            return
        
        # 提取动作信息
        action = data.get('action', {})
        direction = action.get('direction')
        speed = action.get('speed')
        
        # 验证参数
        if not direction or not speed:
            logger.error("VLA命令缺少方向或速度信息")
            return
        
        # 将命令添加到队列
        with self.vla_command_lock:
            self.vla_command_queue.append({
                'direction': direction,
                'speed': speed
            })
        
        logger.info(f"VLA命令已添加到队列: 方向={direction}, 速度={speed}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
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
        """紧急停止"""
        logger.warning("执行紧急停止！")
        
        # 停止自动控制
        if self.auto_controller.is_active:
            self.auto_controller.stop()
        
        # 重置虚拟手柄
        self.virtual_joystick._reset_controls()
        
        # 发送停止指令
        self.mavlink_interface.send_manual_control(0.0, 0.0, 0.0, 0.0)
        
        # 清空VLA命令队列
        with self.vla_command_lock:
            self.vla_command_queue.clear()
        
        logger.info("紧急停止完成")

def main():
    """主函数"""
    try:
        # 创建主控制器
        controller = ROVMainController()
        
        # 启动控制器
        controller.start()
        
        # 主循环
        while controller.is_running:
            try:
                time.sleep(1.0)
                
                # 显示状态信息
                status = controller.get_status()
                if status['mavlink_connected']:
                    vehicle_state = status['vehicle_state']
                    depth = vehicle_state.get('position', {}).get('depth', 0.0)
                    heading = vehicle_state.get('attitude', {}).get('yaw', 0.0) * 180 / 3.14159
                    battery = vehicle_state.get('battery', {}).get('remaining', 0)
                    
                    print(f"\r状态: {status['control_mode']} | 深度: {depth:.2f}m | 航向: {heading:.1f}° | 电池: {battery}%", end='')
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"主循环错误: {e}")
                time.sleep(1.0)
        
    except Exception as e:
        logger.error(f"程序错误: {e}")
    finally:
        # 关闭控制器
        if 'controller' in locals():
            controller.shutdown()

if __name__ == "__main__":
    main()