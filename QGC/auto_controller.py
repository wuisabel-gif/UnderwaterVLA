#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动控制模块
包含PID控制器和自动控制算法，以及MPC控制器
"""

import time
import threading
import numpy as np
from typing import Dict, Any, Optional
import configparser
import logging

logger = logging.getLogger(__name__)

class PIDController:
    """PID控制器类"""
    
    def __init__(self, kp: float, ki: float, kd: float, 
                 output_min: float = -1.0, output_max: float = 1.0):
        """初始化PID控制器"""
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        
        # 状态变量
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
        
    def reset(self):
        """重置控制器状态"""
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = time.time()
    
    def update(self, setpoint: float, current_value: float) -> float:
        """更新PID控制器并返回控制输出"""
        current_time = time.time()
        dt = current_time - self.last_time
        
        if dt <= 0:
            return 0.0
        
        # 计算误差
        error = setpoint - current_value
        
        # 积分项
        self.integral += error * dt
        
        # 微分项
        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0
        
        # PID输出
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        
        # 限制输出范围
        output = max(self.output_min, min(self.output_max, output))
        
        # 更新状态
        self.prev_error = error
        self.last_time = current_time
        
        return output

class MPCController:
    """模型预测控制器类"""
    
    def __init__(self, config: configparser.ConfigParser):
        """初始化MPC控制器"""
        # MPC参数
        self.control_horizon = 1.0  # 控制时域1秒
        self.control_interval = 0.02  # 控制间隔20ms
        self.steps = int(self.control_horizon / self.control_interval)
        
        # 速度映射 (低/中/高速)
        self.speed_map = {
            'low': {'translational': 0.2, 'rotational': 0.5},
            'medium': {'translational': 0.5, 'rotational': 1.0},
            'high': {'translational': 0.8, 'rotational': 1.5}
        }
        
        # 权重参数
        self.beta = config.getfloat('MPC', 'beta', fallback=1.0)  # 跟踪误差权重
        self.gamma = config.getfloat('MPC', 'gamma', fallback=0.1)  # 控制努力权重
        self.delta = config.getfloat('MPC', 'delta', fallback=0.05)  # 流体阻力权重
        
        # 系统参数
        self.mass = config.getfloat('MPC', 'mass', fallback=10.0)  # 系统质量(kg)
        self.inertia = config.getfloat('MPC', 'inertia', fallback=0.5)  # 转动惯量(kg·m²)
        self.translational_drag_coeff = config.getfloat('MPC', 'translational_drag_coeff', fallback=5.0)  # 平移阻力系数
        self.rotational_drag_coeff = config.getfloat('MPC', 'rotational_drag_coeff', fallback=0.1)  # 旋转阻力系数
        
        # 当前状态
        self.current_velocity = 0.0
        self.current_angular_rate = 0.0
        self.estimated_translational_drag = 0.0
        self.estimated_rotational_drag = 0.0
        
        # 控制模式
        self.motion_mode = None  # 'translation' 或 'turning'
        self.target_velocity = 0.0
        self.target_angular_rate = 0.0
        self.reference_profile = []
        
        # 控制状态
        self.is_active = False
        self.start_time = 0.0
        
    def set_vla_command(self, direction: str, speed: str):
        """设置VLA命令并生成参考轨迹"""
        # 重置控制器
        self.is_active = True
        self.start_time = time.time()
        
        # 根据方向确定运动模式
        if direction in ['前', '后']:
            self.motion_mode = 'translation'
            # 获取目标速度
            v_cmd = self.speed_map.get(speed, {}).get('translational', 0.0)
            # 根据方向调整符号
            if direction == '后':
                v_cmd = -v_cmd
            self.target_velocity = v_cmd
            # 生成参考轨迹
            self.reference_profile = self._generate_translational_profile(v_cmd)
        elif direction in ['左', '右']:
            self.motion_mode = 'turning'
            # 获取目标角速度
            r_cmd = self.speed_map.get(speed, {}).get('rotational', 0.0)
            # 根据方向调整符号
            if direction == '左':
                r_cmd = -r_cmd
            self.target_angular_rate = r_cmd
            # 生成参考轨迹
            self.reference_profile = self._generate_rotational_profile(r_cmd)
        elif direction == '停':
            self.motion_mode = 'translation'  # 停止视为平移停止
            self.target_velocity = 0.0
            self.reference_profile = self._generate_translational_profile(0.0)
        else:
            logger.warning(f"未知的方向命令: {direction}")
            self.is_active = False
            return
    
    def _generate_translational_profile(self, v_cmd: float) -> list:
        """生成平移运动参考轨迹"""
        profile = []
        for i in range(self.steps):
            t = i * self.control_interval
            if 0 <= t < 0.2:
                v_ref = v_cmd * min(5 * t, 1)
            elif 0.2 <= t < 0.5:
                v_ref = v_cmd
            elif 0.5 <= t <= 1:
                v_ref = v_cmd * max(1 - 2 * (t - 0.5), 0)
            else:
                v_ref = 0.0
            profile.append(v_ref)
        return profile
    
    def _generate_rotational_profile(self, r_cmd: float) -> list:
        """生成旋转运动参考轨迹"""
        profile = []
        for i in range(self.steps):
            t = i * self.control_interval
            if 0 <= t < 0.2:
                r_ref = r_cmd * min(5 * t, 1)
            elif 0.2 <= t < 0.5:
                r_ref = r_cmd
            elif 0.5 <= t <= 1:
                r_ref = r_cmd * max(1 - 2 * (t - 0.5), 0)
            else:
                r_ref = 0.0
            profile.append(r_ref)
        return profile
    
    def update_state(self, vehicle_state: Dict[str, Any]):
        """更新车辆状态"""
        # 更新当前速度和角速度
        if 'velocity' in vehicle_state:
            velocity = vehicle_state['velocity']
            # 假设我们使用x方向的速度作为平移速度
            self.current_velocity = velocity.get('x', 0.0)
            
        if 'attitude' in vehicle_state:
            attitude = vehicle_state['attitude']
            # 使用偏航角速度
            self.current_angular_rate = attitude.get('yaw_rate', 0.0)
    
    def compute_control(self) -> Dict[str, float]:
        """计算MPC控制输出"""
        if not self.is_active:
            return {'throttle': 0.0, 'yaw': 0.0}
        
        # 计算当前时间
        current_time = time.time()
        elapsed_time = current_time - self.start_time
        
        # 检查是否超过控制时域
        if elapsed_time > self.control_horizon:
            self.is_active = False
            return {'throttle': 0.0, 'yaw': 0.0}
        
        # 计算当前步骤
        step = int(elapsed_time / self.control_interval)
        if step >= len(self.reference_profile):
            step = len(self.reference_profile) - 1
            
        # 获取参考信号
        reference_value = self.reference_profile[step]
        
        # 估计流体阻力
        self._estimate_drag()
        
        # 根据运动模式计算控制输出
        if self.motion_mode == 'translation':
            # 平移运动控制
            thrust = self._compute_translational_control(reference_value)
            return {'throttle': thrust, 'yaw': 0.0}
        elif self.motion_mode == 'turning':
            # 旋转运动控制
            yaw_rate = self._compute_rotational_control(reference_value)
            return {'throttle': 0.0, 'yaw': yaw_rate}
        else:
            return {'throttle': 0.0, 'yaw': 0.0}
    
    def _estimate_drag(self):
        """估计流体阻力"""
        try:
            # 平移阻力估计
            if abs(self.current_velocity) > 0.01:  # 避免除零
                # D_v = (τ_v - M*v_dot) / (v*|v|)
                # 简化实现：使用当前速度和阻力系数计算
                self.estimated_translational_drag = self.translational_drag_coeff * self.current_velocity * abs(self.current_velocity)
            
            # 旋转阻力估计
            if abs(self.current_angular_rate) > 0.01:  # 避免除零
                # D_r = (τ_r - I_z*r_dot) / (r*|r|)
                # 简化实现：使用当前角速度和阻力系数计算
                self.estimated_rotational_drag = self.rotational_drag_coeff * self.current_angular_rate * abs(self.current_angular_rate)
        except Exception as e:
            logger.warning(f"阻力估计错误: {e}")
    
    def _compute_translational_control(self, reference_velocity: float) -> float:
        """计算平移运动控制输出"""
        # 计算跟踪误差
        velocity_error = reference_velocity - self.current_velocity
        
        # 计算MPC优化目标
        # 简化实现：使用比例控制和阻力补偿
        thrust = (self.beta * velocity_error + 
                 self.delta * self.estimated_translational_drag) / self.mass
        
        # 限制输出范围
        thrust = max(-1.0, min(1.0, thrust))
        return thrust
    
    def _compute_rotational_control(self, reference_angular_rate: float) -> float:
        """计算旋转运动控制输出"""
        # 计算跟踪误差
        angular_rate_error = reference_angular_rate - self.current_angular_rate
        
        # 计算MPC优化目标
        # 简化实现：使用比例控制和阻力补偿
        yaw_rate = (self.beta * angular_rate_error + 
                   self.delta * self.estimated_rotational_drag) / self.inertia
        
        # 限制输出范围
        yaw_rate = max(-1.0, min(1.0, yaw_rate))
        return yaw_rate

class AutoController:
    """自动控制器类"""
    
    def __init__(self, config_file: str = 'config.ini'):
        """初始化自动控制器"""
        self.config = configparser.ConfigParser(inline_comment_prefixes=('#', ';'))
        self.config.read(config_file, encoding='utf-8')
        
        # 控制参数
        self.control_frequency = self.config.getint('Control', 'control_frequency')
        self.max_throttle = self.config.getint('Control', 'max_throttle') / 100.0
        self.max_yaw_rate = self.config.getfloat('Control', 'max_yaw_rate')
        self.max_pitch_angle = self.config.getfloat('Control', 'max_pitch_angle')
        self.max_roll_angle = self.config.getfloat('Control', 'max_roll_angle')
        
        # 自动控制参数
        self.enable_depth_hold = self.config.getboolean('AutoControl', 'enable_depth_hold')
        self.target_depth = self.config.getfloat('AutoControl', 'target_depth')
        self.depth_tolerance = self.config.getfloat('AutoControl', 'depth_tolerance')
        self.enable_heading_hold = self.config.getboolean('AutoControl', 'enable_heading_hold')
        self.target_heading = self.config.getfloat('AutoControl', 'target_heading')
        self.heading_tolerance = self.config.getfloat('AutoControl', 'heading_tolerance')
        
        # 安全参数
        self.emergency_stop_timeout = self.config.getfloat('Safety', 'emergency_stop_timeout')
        self.max_depth = self.config.getfloat('Safety', 'max_depth')
        self.min_depth = self.config.getfloat('Safety', 'min_depth')
        
        # 初始化控制器
        self._init_controllers()
        
        # 控制状态
        self.is_active = False
        self.control_thread = None
        self.last_control_time = 0
        self.emergency_stop_time = 0
        
        # 控制输出
        self.control_outputs = {
            'roll': 0.0,
            'pitch': 0.0,
            'throttle': 0.0,
            'yaw': 0.0
        }
    
    def _init_controllers(self):
        """初始化控制器"""
        # PID控制器
        self._init_pid_controllers()
        
        # MPC控制器
        self.mpc_controller = MPCController(self.config)
    
    def _init_pid_controllers(self):
        """初始化PID控制器"""
        # 深度控制PID (俯仰控制)
        self.depth_pid = PIDController(
            kp=0.5,    # 比例增益
            ki=0.1,    # 积分增益
            kd=0.2,    # 微分增益
            output_min=-0.5,
            output_max=0.5
        )
        
        # 航向控制PID (偏航控制)
        self.heading_pid = PIDController(
            kp=0.8,    # 比例增益
            ki=0.05,   # 积分增益
            kd=0.3,    # 微分增益
            output_min=-0.8,
            output_max=0.8
        )
        
        # 横滚稳定PID
        self.roll_pid = PIDController(
            kp=1.0,    # 比例增益
            ki=0.0,    # 积分增益
            kd=0.5,    # 微分增益
            output_min=-0.3,
            output_max=0.3
        )
    
    def start(self):
        """启动自动控制"""
        if self.is_active:
            logger.warning("自动控制已经在运行")
            return
        
        self.is_active = True
        self.control_thread = threading.Thread(target=self._control_loop, daemon=True)
        self.control_thread.start()
        logger.info("自动控制已启动")
    
    def stop(self):
        """停止自动控制"""
        self.is_active = False
        if self.control_thread:
            self.control_thread.join(timeout=1.0)
        
        # 重置所有控制器
        self.depth_pid.reset()
        self.heading_pid.reset()
        self.roll_pid.reset()
        self.mpc_controller.is_active = False
        
        # 清零控制输出
        self.control_outputs = {'roll': 0.0, 'pitch': 0.0, 'throttle': 0.0, 'yaw': 0.0}
        
        logger.info("自动控制已停止")
    
    def _control_loop(self):
        """主控制循环"""
        while self.is_active:
            try:
                current_time = time.time()
                
                # 控制频率限制
                if current_time - self.last_control_time < 1.0 / self.control_frequency:
                    time.sleep(0.01)
                    continue
                
                # 执行自动控制逻辑
                self._execute_auto_control()
                
                self.last_control_time = current_time
                
            except Exception as e:
                logger.error(f"控制循环错误: {e}")
                time.sleep(0.1)
    
    def _execute_auto_control(self):
        """执行自动控制逻辑"""
        # 从外部获取当前车辆状态
        # 这些值应该通过update_vehicle_state方法更新
        current_depth = getattr(self, '_current_depth', 0.0)
        current_heading = getattr(self, '_current_heading', 0.0)
        current_roll = getattr(self, '_current_roll', 0.0)
        
        # 深度保持控制
        if self.enable_depth_hold:
            depth_error = abs(self.target_depth - current_depth)
            if depth_error > self.depth_tolerance:
                pitch_output = self.depth_pid.update(self.target_depth, current_depth)
                self.control_outputs['pitch'] = pitch_output
            else:
                self.control_outputs['pitch'] = 0.0
        
        # 航向保持控制
        if self.enable_heading_hold:
            heading_error = abs(self.target_heading - current_heading)
            if heading_error > self.heading_tolerance:
                yaw_output = self.heading_pid.update(self.target_heading, current_heading)
                self.control_outputs['yaw'] = yaw_output
            else:
                self.control_outputs['yaw'] = 0.0
        
        # 横滚稳定控制
        roll_output = self.roll_pid.update(0.0, current_roll)
        self.control_outputs['roll'] = roll_output
        
        # MPC控制
        if self.mpc_controller.is_active:
            mpc_outputs = self.mpc_controller.compute_control()
            self.control_outputs['throttle'] = mpc_outputs['throttle']
            self.control_outputs['yaw'] += mpc_outputs['yaw']  # 与航向保持叠加
            
            # 限制输出范围
            self.control_outputs['throttle'] = max(-1.0, min(1.0, self.control_outputs['throttle']))
            self.control_outputs['yaw'] = max(-1.0, min(1.0, self.control_outputs['yaw']))
        
        # 安全检查
        self._safety_check()
    
    def _safety_check(self):
        """安全检查"""
        current_time = time.time()
        
        # 深度限制检查
        current_depth = getattr(self, '_current_depth', 0.0)
        if current_depth < self.max_depth or current_depth > self.min_depth:
            logger.warning(f"深度超出安全范围: {current_depth}m")
            self._emergency_stop()
            return
        
        # 紧急停止超时检查
        if self.emergency_stop_time > 0 and current_time - self.emergency_stop_time > self.emergency_stop_timeout:
            logger.warning("紧急停止超时，恢复正常控制")
            self.emergency_stop_time = 0
    
    def _emergency_stop(self):
        """紧急停止"""
        logger.warning("执行紧急停止！")
        self.emergency_stop_time = time.time()
        
        # 清零所有控制输出
        self.control_outputs = {'roll': 0.0, 'pitch': 0.0, 'throttle': 0.0, 'yaw': 0.0}
        
        # 重置控制器
        self.depth_pid.reset()
        self.heading_pid.reset()
        self.roll_pid.reset()
        self.mpc_controller.is_active = False
    
    def set_target_depth(self, depth: float):
        """设置目标深度"""
        if self.min_depth <= depth <= self.max_depth:
            self.target_depth = depth
            logger.info(f"目标深度设置为: {depth}m")
        else:
            logger.warning(f"目标深度 {depth}m 超出安全范围")
    
    def set_target_heading(self, heading: float):
        """设置目标航向"""
        # 标准化航向到0-360度
        heading = heading % 360
        self.target_heading = heading
        logger.info(f"目标航向设置为: {heading}°")
    
    def execute_vla_command(self, direction: str, speed: str):
        """执行VLA命令"""
        logger.info(f"执行VLA命令: 方向={direction}, 速度={speed}")
        self.mpc_controller.set_vla_command(direction, speed)
    
    def update_vehicle_state(self, vehicle_state: Dict[str, Any]):
        """更新车辆状态（供外部调用）"""
        # 更新当前状态值
        if 'position' in vehicle_state and 'depth' in vehicle_state['position']:
            self._current_depth = vehicle_state['position']['depth']
        
        if 'attitude' in vehicle_state and 'yaw' in vehicle_state['attitude']:
            yaw = vehicle_state['attitude']['yaw']
            # 转换为0-360度
            self._current_heading = (yaw * 180 / 3.14159) % 360
        
        if 'attitude' in vehicle_state and 'roll' in vehicle_state['attitude']:
            self._current_roll = vehicle_state['attitude']['roll']
            
        # 更新MPC控制器状态
        self.mpc_controller.update_state(vehicle_state)
    
    def get_control_outputs(self) -> Dict[str, float]:
        """获取当前控制输出"""
        return self.control_outputs.copy()