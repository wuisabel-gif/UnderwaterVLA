#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
虚拟手柄模块
模拟手柄输入，提供键盘和鼠标控制
"""

import time
import threading
import pygame
import keyboard
from typing import Dict, Any, Callable, Optional
import logging

logger = logging.getLogger(__name__)

class VirtualJoystick:
    """虚拟手柄类"""
    
    def __init__(self):
        """初始化虚拟手柄"""
        # 初始化Pygame
        pygame.init()
        
        # 手柄状态
        self.joystick_state = {
            'roll': 0.0,      # 横滚 (-1.0 到 1.0)
            'pitch': 0.0,     # 俯仰 (-1.0 到 1.0)
            'throttle': 0.0,  # 油门 (-1.0 到 1.0)
            'yaw': 0.0,       # 偏航 (-1.0 到 1.0)
            'buttons': {}      # 按钮状态
        }
        
        # 控制参数
        self.control_sensitivity = 0.1  # 控制灵敏度
        self.return_to_center = True    # 是否自动回中
        self.return_speed = 0.05        # 回中速度
        
        # 控制状态
        self.is_active = False
        self.control_thread = None
        
        # 回调函数
        self.control_callback = None
        
        # 键盘映射
        self.key_mapping = {
            'w': 'pitch_forward',      # W键 - 俯仰向前
            's': 'pitch_backward',     # S键 - 俯仰向后
            'a': 'roll_left',          # A键 - 横滚向左
            'd': 'roll_right',         # D键 - 横滚向右
            'q': 'yaw_left',           # Q键 - 偏航向左
            'e': 'yaw_right',          # E键 - 偏航向右
            'space': 'throttle_up',    # 空格键 - 油门增加
            'shift': 'throttle_down',  # Shift键 - 油门减少
            'r': 'reset_controls',     # R键 - 重置控制
            'esc': 'emergency_stop'    # ESC键 - 紧急停止
        }
        
        # 设置键盘监听
        self._setup_keyboard_listeners()
    
    def _setup_keyboard_listeners(self):
        """设置键盘监听器"""
        for key, action in self.key_mapping.items():
            if key == 'shift':
                keyboard.on_press_key('shift', lambda e: self._handle_key_action(action))
                keyboard.on_release_key('shift', lambda e: self._handle_key_release(action))
            elif key == 'space':
                keyboard.on_press_key('space', lambda e: self._handle_key_action(action))
                keyboard.on_release_key('space', lambda e: self._handle_key_release(action))
            else:
                keyboard.on_press_key(key, lambda e, a=action: self._handle_key_action(a))
                keyboard.on_release_key(key, lambda e, a=action: self._handle_key_release(a))
    
    def _handle_key_action(self, action: str):
        """处理按键按下事件"""
        if action == 'pitch_forward':
            self.joystick_state['pitch'] = min(1.0, self.joystick_state['pitch'] + self.control_sensitivity)
        elif action == 'pitch_backward':
            self.joystick_state['pitch'] = max(-1.0, self.joystick_state['pitch'] - self.control_sensitivity)
        elif action == 'roll_left':
            self.joystick_state['roll'] = max(-1.0, self.joystick_state['roll'] - self.control_sensitivity)
        elif action == 'roll_right':
            self.joystick_state['roll'] = min(1.0, self.joystick_state['roll'] + self.control_sensitivity)
        elif action == 'yaw_left':
            self.joystick_state['yaw'] = max(-1.0, self.joystick_state['yaw'] - self.control_sensitivity)
        elif action == 'yaw_right':
            self.joystick_state['yaw'] = min(1.0, self.joystick_state['yaw'] + self.control_sensitivity)
        elif action == 'throttle_up':
            self.joystick_state['throttle'] = min(1.0, self.joystick_state['throttle'] + self.control_sensitivity)
        elif action == 'throttle_down':
            self.joystick_state['throttle'] = max(-1.0, self.joystick_state['throttle'] - self.control_sensitivity)
        elif action == 'reset_controls':
            self._reset_controls()
        elif action == 'emergency_stop':
            self._emergency_stop()
    
    def _handle_key_release(self, action: str):
        """处理按键释放事件"""
        # 对于需要持续按住的按键，这里可以添加逻辑
        pass
    
    def _reset_controls(self):
        """重置所有控制"""
        self.joystick_state['roll'] = 0.0
        self.joystick_state['pitch'] = 0.0
        self.joystick_state['throttle'] = 0.0
        self.joystick_state['yaw'] = 0.0
        logger.info("控制已重置")
    
    def _emergency_stop(self):
        """紧急停止"""
        self._reset_controls()
        logger.warning("紧急停止已执行！")
    
    def start(self):
        """启动虚拟手柄"""
        if self.is_active:
            logger.warning("虚拟手柄已经在运行")
            return
        
        self.is_active = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        logger.info("虚拟手柄已启动")
        logger.info("控制说明:")
        logger.info("W/S - 俯仰控制")
        logger.info("A/D - 横滚控制")
        logger.info("Q/E - 偏航控制")
        logger.info("空格/Shift - 油门控制")
        logger.info("R - 重置控制")
        logger.info("ESC - 紧急停止")
    
    def stop(self):
        """停止虚拟手柄"""
        self.is_active = False
        if self.control_thread:
            self.control_thread.join(timeout=1.0)
        
        # 重置控制
        self._reset_controls()
        logger.info("虚拟手柄已停止")
    
    def _control_loop(self):
        """主控制循环"""
        while self.is_active:
            try:
                # 自动回中逻辑
                if self.return_to_center:
                    self._auto_return_to_center()
                
                # 调用回调函数
                if self.control_callback:
                    self.control_callback(self.joystick_state)
                
                time.sleep(0.02)  # 50Hz更新频率
                
            except Exception as e:
                logger.error(f"控制循环错误: {e}")
                time.sleep(0.1)
    
    def _auto_return_to_center(self):
        """自动回中"""
        for axis in ['roll', 'pitch', 'yaw']:
            if abs(self.joystick_state[axis]) > 0.01:
                if self.joystick_state[axis] > 0:
                    self.joystick_state[axis] = max(0, self.joystick_state[axis] - self.return_speed)
                else:
                    self.joystick_state[axis] = min(0, self.joystick_state[axis] + self.return_speed)
            else:
                self.joystick_state[axis] = 0.0
    
    def set_control_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """设置控制回调函数"""
        self.control_callback = callback
    
    def get_joystick_state(self) -> Dict[str, Any]:
        """获取当前手柄状态"""
        return self.joystick_state.copy()
    
    def set_control_sensitivity(self, sensitivity: float):
        """设置控制灵敏度"""
        self.control_sensitivity = max(0.01, min(1.0, sensitivity))
        logger.info(f"控制灵敏度设置为: {self.control_sensitivity}")
    
    def set_return_to_center(self, enabled: bool):
        """设置是否自动回中"""
        self.return_to_center = enabled
        logger.info(f"自动回中: {'启用' if enabled else '禁用'}")
    
    def set_return_speed(self, speed: float):
        """设置回中速度"""
        self.return_speed = max(0.01, min(0.5, speed))
        logger.info(f"回中速度设置为: {self.return_speed}")
    
    def set_manual_control(self, roll: float, pitch: float, throttle: float, yaw: float):
        """手动设置控制值"""
        self.joystick_state['roll'] = max(-1.0, min(1.0, roll))
        self.joystick_state['pitch'] = max(-1.0, min(1.0, pitch))
        self.joystick_state['throttle'] = max(-1.0, min(1.0, throttle))
        self.joystick_state['yaw'] = max(-1.0, min(1.0, yaw))
    
    def cleanup(self):
        """清理资源"""
        self.stop()
        pygame.quit()
