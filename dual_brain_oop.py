import json
import time
import os
from PIL import ImageGrab
import io
import base64
from openai import OpenAI
from dual_brain_core import *

class DualBrainController:
    """双脑控制器类，协调大脑和小脑工作"""
    
    def __init__(self):
        self.big_brain = BigBrain()
        self.small_brain = SmallBrain()
        
    def run_task_cycle(self, instruction):
        # 执行单次任务循环（串联模式）
        
        try:
            image_base64_1,IMG1 = self.big_brain.encode_image_to_base64()
            image_base64_2,IMG2 = self.big_brain.encode_image_to_base64()
        except Exception as e:
            print(f"Error reading image files: {e}")
            print("请确保图像文件存在且可访问")
            return None, True  # 返回错误信号，停止循环
        
        # 首先调用大脑生成任务规划
        print("正在生成任务规划...")
        try:
            task_plan = self.big_brain.call_qvqmax_api_for_planning(image_base64_1, instruction, image_base64_2)
            self.big_brain.log_decision(task_plan)
        except Exception as e:
            print("请检查QVQMAX API是否正常,没网咯")
            task_plan=None
        if task_plan:
            print("任务规划生成成功:")
            print(json.dumps(task_plan, indent=2, ensure_ascii=False))
        else:
            print("任务规划生成失败，将直接执行决策")
        
        # 持续执行直到任务完成
        task_completed = False
        step_count = 1
        
        while not task_completed:
            print(f"\n执行步骤 {step_count}")
            
            # 只调用小脑API执行决策
            decision_response = self.small_brain.call_lmstudio_api(image_base64_1, instruction, task_plan, step_count, image_base64_2)
            
            # 执行决策
            if decision_response:
                image_base64_1, image_base64_2= self.small_brain.execute_decision(decision_response)
                
                # 检查任务是否完成
                status = decision_response.get('status', '')
                if status == '任务完成':
                    print("任务已完成，退出当前循环")
                    task_completed = True
                    return decision_response, True  # 任务完成，停止循环
                
                # 检查步骤是否完成，如果完成则增加步骤计数
                step_completed = decision_response.get('step_completed', True)
                if not step_completed:
                    print(f"步骤 {step_count} 未完成")
                else:
                    step_count += 1
                

            else:
                print("决策API调用失败或超时，无法做出决策。")
                # 添加一个默认的响应以避免程序完全停止
                decision_response = {
                    "action": {
                        "direction": "停",
                        "speed": "stop",
                        "confidence": 0.0
                    },
                    "status": "任务中",
                    "reasoning": "API调用失败，使用默认停止指令"
                }
                self.small_brain.execute_decision(decision_response)
                return None, True  # 返回错误信号，停止循环

    def run(self):
        """运行主程序"""
        while True:
            # 外层循环：接收键盘输入指令
            print("\n请输入指令（输入'退出'结束程序）:")
            print("可选预设指令: exp1, exp2, exp3")
            user_input = input().strip()
            
            if user_input == '退出':
                print("程序结束")
                break
                
            # 根据输入选择指令
            if user_input in self.big_brain.preset_instructions:
                instruction = self.big_brain.preset_instructions[user_input]
                print(f"选择了预设指令 {user_input}: {instruction}")
                print("5s SHOOT")
                time.sleep(5)
            else:
                # 如果不是预设指令，则将用户输入作为自定义指令
                instruction = user_input
                print(f"使用自定义指令: {instruction}")
                
            # 内层循环：执行任务直到模型回复"任务完成"
            task_completed = False
            while not task_completed:
                # 执行任务循环
                decision_response, should_break = self.run_task_cycle(instruction)
                
                if should_break:
                    if decision_response and decision_response.get('status') == '任务完成':
                        task_completed = True
                    else:
                        break
                
                # 添加短暂延迟避免API调用过于频繁
                time.sleep(1)


def main():
    # 创建双脑控制器实例
    controller = DualBrainController()
    
    # 运行主程序
    controller.run()


if __name__ == "__main__":
    main()