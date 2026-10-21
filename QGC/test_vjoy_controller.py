"""
测试 joy.py 中的 VJoyController 类
确保 vJoy 设备能被 QGroundControl 正确识别并控制
"""

import time
import sys
import os

# 将当前脚本目录添加到 sys.path，以便导入同目录下的 joy.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from joy import VJoyController

def test_basic_movement():
    """测试基本的摇杆移动和按钮按压"""
    print("=== vJoy Controller 测试 ===")
    try:
        # 1. 初始化控制器
        print("1. 初始化 vJoy 设备...")
        controller = VJoyController(device_id=1)
        print("   vJoy 设备初始化成功。")
        time.sleep(1) # 等待一下，确保初始化完成

        # 2. 测试左摇杆 (X, Y) - 向右移动
        print("2. 测试左摇杆向右移动...")
        controller.set_axis('x', 1.0) # X轴最大值 (右)
        controller.set_axis('y', 0.0) # Y轴居中
        controller.update()
        print("   左摇杆 X 轴设置为 1.0 (右), Y 轴居中。")
        time.sleep(2) # 保持2秒

        # 3. 测试左摇杆 (X, Y) - 向左移动
        print("3. 测试左摇杆向左移动...")
        controller.set_axis('x', -1.0) # X轴最小值 (左)
        controller.set_axis('y', 0.0)  # Y轴居中
        controller.update()
        print("   左摇杆 X 轴设置为 -1.0 (左), Y 轴居中。")
        time.sleep(2) # 保持2秒

        # 4. 测试左摇杆 (X, Y) - 居中
        print("4. 测试左摇杆居中...")
        controller.set_axis('x', 0.0) # X轴居中
        controller.set_axis('y', 0.0) # Y轴居中
        controller.update()
        print("   左摇杆 X, Y 轴设置为 0.0 (居中)。")
        time.sleep(1)

        # 5. 测试右摇杆 (RX, RY) - 向上移动
        print("5. 测试右摇杆向上移动...")
        controller.set_axis('rx', 0.0)  # RX轴居中
        controller.set_axis('ry', -1.0) # RY轴最小值 (上)
        controller.update()
        print("   右摇杆 RX 轴居中, RY 轴设置为 -1.0 (上)。")
        time.sleep(2) # 保持2秒

        # 6. 测试右摇杆 (RX, RY) - 居中
        print("6. 测试右摇杆居中...")
        controller.set_axis('rx', 0.0) # RX轴居中
        controller.set_axis('ry', 0.0) # RY轴居中
        controller.update()
        print("   右摇杆 RX, RY 轴设置为 0.0 (居中)。")
        time.sleep(1)

        # 7. 测试按钮按压
        print("7. 测试按下并释放按钮 1...")
        controller.press_button(1, True) # 按下按钮1
        controller.update()
        print("   按钮 1 已按下。")
        time.sleep(1) # 保持1秒

        controller.press_button(1, False) # 释放按钮1
        controller.update()
        print("   按钮 1 已释放。")
        time.sleep(1)

        # 8. 测试按钮按压 (按钮2)
        print("8. 测试按下并释放按钮 2...")
        controller.press_button(2, True) # 按下按钮2
        controller.update()
        print("   按钮 2 已按下。")
        time.sleep(1) # 保持1秒

        controller.press_button(2, False) # 释放按钮2
        controller.update()
        print("   按钮 2 已释放。")
        time.sleep(1)

        # 9. 重置并关闭
        print("9. 重置并关闭设备...")
        controller.reset()
        controller.close()
        print("   设备已重置并关闭。")

        print("\n=== 测试完成 ===")
        print("请在 QGroundControl 中观察手柄输入是否被正确识别和响应。")

    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_basic_movement()