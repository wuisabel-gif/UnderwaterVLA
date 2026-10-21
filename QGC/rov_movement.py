from RovController import RovController
import time

class RovMovement:
    def __init__(self):
        """初始化ROV移动控制器"""
        self.controller = RovController()
        self.controller.arm()  # 初始化时解锁ROV
        
    def move(self, direction, speed, duration):
        """
        控制ROV按指定方向、速度移动指定时间
        
        参数:
        direction (str): 移动方向，可选值：
            - 'forward' - 前进
            - 'backward' - 后退
            - 'left' - 左移
            - 'right' - 右移
            - 'up' - 上浮
            - 'down' - 下潜
            - 'turn_left' - 左转
            - 'turn_right' - 右转
        speed (int): 移动速度，范围0-1000
        duration (float): 移动持续时间，单位：秒
        """
        # 保存原始速度
        original_speed = self.controller.default_speed
        
        try:
            # 设置新的速度
            self.controller.default_speed = min(max(speed, 0), 1000)
            
            # 根据方向执行相应的移动命令
            movement_functions = {
                'forward': self.controller.move_forward,
                'backward': self.controller.move_backward,
                'left': self.controller.move_left,
                'right': self.controller.move_right,
                'up': self.controller.move_up,
                'down': self.controller.move_down,
                'turn_left': self.controller.turn_left,
                'turn_right': self.controller.turn_right
            }
            
            if direction not in movement_functions:
                raise ValueError(f"无效的移动方向: {direction}")
            
            # 执行移动
            movement_functions[direction]()
            
            # 等待指定时间
            time.sleep(duration)
            
            # 停止移动
            self.controller.stop()
            
        finally:
            # 恢复原始速度
            self.controller.default_speed = original_speed
    
    def stop(self):
        """停止所有移动"""
        self.controller.stop()
    
    def close(self):
        """关闭控制器并锁定ROV"""
        self.controller.stop()
        self.controller.disarm()

# 使用示例
if __name__ == "__main__":
    # 创建ROV移动控制器
    rov = RovMovement()
    
    try:
        # 前进示例：速度500，持续2秒
        rov.move('forward', 500, 2)
        
        # 上浮示例：速度300，持续1.5秒
        rov.move('up', 300, 1.5)
        
        # 左转示例：速度400，持续1秒
        rov.move('turn_left', 400, 1)
        
    finally:
        # 确保程序结束时正确关闭控制器
        rov.close()
