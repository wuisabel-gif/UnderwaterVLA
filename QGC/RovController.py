class RovController:
    def __init__(self):
        self.default_speed = 500
        print("模拟ROV控制器已初始化")
        
    def arm(self):
        print("模拟ROV已解锁")
        
    def disarm(self):
        print("模拟ROV已锁定")
        
    def move_forward(self):
        print(f"模拟ROV前进，速度: {self.default_speed}")
        
    def move_backward(self):
        print(f"模拟ROV后退，速度: {self.default_speed}")
        
    def move_left(self):
        print(f"模拟ROV左移，速度: {self.default_speed}")
        
    def move_right(self):
        print(f"模拟ROV右移，速度: {self.default_speed}")
        
    def move_up(self):
        print(f"模拟ROV上浮，速度: {self.default_speed}")
        
    def move_down(self):
        print(f"模拟ROV下潜，速度: {self.default_speed}")
        
    def turn_left(self):
        print(f"模拟ROV左转，速度: {self.default_speed}")
        
    def turn_right(self):
        print(f"模拟ROV右转，速度: {self.default_speed}")
        
    def stop(self):
        print("模拟ROV停止")