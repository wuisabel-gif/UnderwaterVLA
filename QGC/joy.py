import pyvjoy
import time
import json

class VJoyController:
    def __init__(self, device_id=1):
        """
        初始化虚拟手柄
        :param device_id: vJoy 设备 ID（默认为 1）
        """
        try:
            self.device = pyvjoy.VJoyDevice(device_id)
            self.reset()
            print("vJoy 设备初始化成功")
        except Exception as e:
            raise RuntimeError(f"vJoy 初始化失败: {e}")

    def reset(self):
        """重置摇杆和按钮状态"""
        self.device.reset()
        self.device.update()

    def set_axis(self, axis, value):
        """
        设置摇杆轴值（归一化范围：-1.0 到 1.0）
        :param axis: 轴名称（如 'x', 'y', 'rx', 'ry'）
        :param value: 归一化值（自动映射到 vJoy 的 1-32768 范围）
        """
        axis_map = {
            'x': pyvjoy.HID_USAGE_X,
            'y': pyvjoy.HID_USAGE_Y,
            'z': pyvjoy.HID_USAGE_Z,
            'rx': pyvjoy.HID_USAGE_RX,
            'ry': pyvjoy.HID_USAGE_RY,
            'rz': pyvjoy.HID_USAGE_RZ,
        }
        if axis not in axis_map:
            raise ValueError(f"不支持的轴名称: {axis}")
        
        # 将归一化值 (-1~1) 映射到 vJoy 的 1-32768 范围
        scaled_value = int((value + 1) * 16384)  # 16384 = 32768/2
        self.device.set_axis(axis_map[axis], scaled_value)

    def press_button(self, button_id, state=True):
        """
        按下/释放按钮
        :param button_id: 按钮编号（从 1 开始）
        :param state: True（按下）或 False（释放）
        """
        self.device.set_button(button_id, state)

    def update(self):
        """提交当前所有输入状态"""
        self.device.update()

    def close(self):
        """关闭设备"""
        self.reset()
        self.device = None

    def execute_from_json(self, json_input):
        """
        从JSON输入中提取速度和方向，并执行相应的操作
        :param json_input: 包含方向和速度信息的JSON字符串或字典
        """
        # 如果输入是字符串，则解析为字典
        if isinstance(json_input, str):
            try:
                data = json.loads(json_input)
            except json.JSONDecodeError as e:
                raise ValueError(f"无效的JSON输入: {e}")
        elif isinstance(json_input, dict):
            data = json_input
        else:
            raise TypeError("输入必须是JSON字符串或字典")
        
        # 提取动作信息
        action = data.get('action', {})
        direction = action.get('direction')
        speed = action.get('speed')
        
        # 方向到轴映射
        direction_map = {
            '前': {'axis': 'y', 'value': -1.0},  # 前进，Y轴负方向
            '后': {'axis': 'y', 'value': 1.0},   # 后退，Y轴正方向
            '左': {'axis': 'x', 'value': -1.0},  # 左移，X轴负方向
            '右': {'axis': 'x', 'value': 1.0},   # 右移，X轴正方向
            '停': {'axis': 'y', 'value': 0.0}    # 停止，所有轴归零
        }
        
        # 速度到数值映射
        speed_map = {
            'low': 0.3,
            'medium': 0.8,
            'high': 1.0,
            'stop': 0.0
        }
        
        # 重置设备
        self.reset()
        
        # 如果方向是"停"，则所有轴归零
        if direction == '停':
            self.set_axis('x', 0.0)
            self.set_axis('y', 0.0)
        else:
            # 根据方向和速度设置轴值
            if direction in direction_map and speed in speed_map:
                axis_info = direction_map[direction]
                speed_value = speed_map[speed]
                # 应用速度系数到轴值
                adjusted_value = axis_info['value'] * speed_value
                self.set_axis(axis_info['axis'], adjusted_value)
                
                # 如果是斜向移动，可能需要同时设置X和Y轴
                # 此实现假设基础方向是单一轴向移动
                
            else:
                raise ValueError("无效的方向或速度值")
        
        # 提交输入状态
        self.update()
        print(f"执行动作: 方向={direction}, 速度={speed}")

# 示例用法
if __name__ == "__main__":
    # 初始化虚拟手柄
    controller = VJoyController()

    # 示例JSON输入
    json_input = {
        "reasoning": "前进避障",
        "action": {
            "direction": "前",
            "speed": "medium",
            "confidence": 0.9
        },
        "status": "任务中",
        "step_completed": True
    }
    
    # 执行动作
    controller.execute_from_json(json_input)
    
    # 保持状态 2 秒后释放
    time.sleep(2)
    controller.reset()
    controller.close()