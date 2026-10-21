# ArduSub ROV 自动控制系统

这是一个用于控制ArduSub水下ROV的Python自动控制系统，可以替代外接手柄，实现智能算法自动控制。

## 功能特性

- **MAVLink通信**: 通过MAVLink协议与ArduSub通信
- **虚拟手柄**: 使用键盘模拟手柄输入
- **自动控制**: 内置PID控制器，支持深度保持、航向保持等
- **安全保护**: 深度限制、紧急停止等安全功能
- **模式切换**: 支持手动控制和自动控制模式切换
- **可扩展**: 易于集成自定义智能算法

## 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   虚拟手柄模块   │    │   主控制器      │    │  MAVLink接口    │
│ VirtualJoystick │───▶│ MainController  │───▶│ MavlinkInterface│
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   自动控制器    │
                       │ AutoController  │
                       └─────────────────┘
```

## 安装要求

### 系统要求
- Python 3.7+
- Windows/Linux/macOS

### 依赖包
```bash
pip install -r requirements.txt
```

### 主要依赖
- `pymavlink`: MAVLink通信
- `pygame`: 虚拟手柄支持
- `keyboard`: 键盘监听
- `numpy`: 数值计算
- `opencv-python`: 计算机视觉支持（可选）

## 配置说明

### 连接配置 (config.ini)
```ini
[Connection]
connection_type = udp          # 连接类型: udp 或 serial
udp_host = 127.0.0.1         # UDP主机地址
udp_port = 14550              # UDP端口
serial_port = COM3            # 串口端口
baud_rate = 115200            # 波特率

[Control]
control_frequency = 10        # 控制频率 (Hz)
max_throttle = 100            # 最大油门百分比
max_yaw_rate = 45             # 最大偏航角速度 (度/秒)
max_pitch_angle = 30          # 最大俯仰角 (度)
max_roll_angle = 30           # 最大横滚角 (度)

[AutoControl]
enable_depth_hold = true      # 启用深度保持
target_depth = -2.0           # 目标深度 (米)
depth_tolerance = 0.1         # 深度容差 (米)
enable_heading_hold = true    # 启用航向保持
target_heading = 0            # 目标航向 (度)
heading_tolerance = 5         # 航向容差 (度)

[Safety]
emergency_stop_timeout = 5.0  # 紧急停止超时 (秒)
max_depth = -10.0             # 最大深度限制 (米)
min_depth = -0.5              # 最小深度限制 (米)
```

## 使用方法

### 1. 基本启动
```bash
python main_controller.py
```

### 2. 运行示例
```bash
python example_usage.py
```

### 3. 手动控制
启动后默认进入手动控制模式：
- **W/S**: 俯仰控制（前/后）
- **A/D**: 横滚控制（左/右）
- **Q/E**: 偏航控制（左/右）
- **空格/Shift**: 油门控制（上/下）
- **R**: 重置所有控制
- **ESC**: 紧急停止
- **M**: 切换手动/自动模式

### 4. 自动控制
```python
from main_controller import ROVMainController

# 创建控制器
controller = ROVMainController()

# 启动
controller.start()

# 切换到自动模式
controller.set_control_mode('auto')

# 设置目标
controller.set_target_depth(-2.0)    # 目标深度2米
controller.set_target_heading(90.0)  # 目标航向90度

# 关闭
controller.shutdown()
```

## 自定义算法集成

### 1. 继承AutoController类
```python
from auto_controller import AutoController

class MyCustomController(AutoController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # 添加自定义初始化代码
    
    def _execute_auto_control(self):
        # 实现您的智能算法
        # 例如：基于视觉的目标跟踪
        # 例如：基于声纳的障碍物避免
        pass
```

### 2. 集成到主控制器
```python
from main_controller import ROVMainController

class CustomROVController(ROVMainController):
    def __init__(self, config_file='config.ini'):
        super().__init__(config_file)
        # 替换为自定义控制器
        self.auto_controller = MyCustomController(config_file)
```

## 安全注意事项

1. **深度限制**: 系统会自动限制ROV的最大和最小深度
2. **紧急停止**: 按ESC键或检测到异常时自动执行紧急停止
3. **连接监控**: 自动检测MAVLink连接状态，连接丢失时自动重连
4. **超时保护**: 紧急停止后自动恢复控制

## 故障排除

### 常见问题

1. **MAVLink连接失败**
   - 检查QGroundControl是否运行
   - 确认UDP端口设置正确
   - 检查防火墙设置

2. **控制无响应**
   - 确认ROV已解锁
   - 检查控制模式设置
   - 查看日志文件

3. **自动控制不稳定**
   - 调整PID参数
   - 检查传感器数据
   - 确认目标值设置合理

### 日志文件
系统运行时会生成 `rov_control.log` 日志文件，包含详细的运行信息和错误记录。

## 开发说明

### 代码结构
```
QGC/
├── requirements.txt          # 依赖包列表
├── config.ini               # 配置文件
├── mavlink_interface.py     # MAVLink通信接口
├── auto_controller.py       # 自动控制器
├── virtual_joystick.py      # 虚拟手柄
├── main_controller.py       # 主控制器
├── example_usage.py         # 使用示例
└── README.md                # 说明文档
```

### 扩展开发
1. **添加新的控制算法**: 继承AutoController类
2. **集成新的传感器**: 修改MavlinkInterface类
3. **自定义控制界面**: 扩展VirtualJoystick类
4. **添加新的安全功能**: 在主控制器中添加

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至项目维护者

---

**注意**: 使用本系统控制ROV时，请确保在安全的环境中进行，并遵守相关的水下操作规范。
