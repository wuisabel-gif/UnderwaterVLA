import json
import time
from dual_brain_core import BigBrain, SmallBrain, BaseBrain


class DualBrainController:
    """双脑控制器类，协调大脑和小脑工作"""

    def __init__(self, backend=None, image_source=None, settle_time: float = 2.0,
                 interactive: bool = False, max_steps: int = 50, use_planner: bool = True):
        """
        Args:
            backend: rov_backend.RovBackend 实例（None = 打印模拟）
            image_source: image_source.ImageSource 实例或字符串（None = 屏幕截图）
            settle_time: 每个动作后等待多少秒再抓图
            interactive: True 时每个动作后需要按回车确认
            max_steps: 单个任务最多执行多少个动作，超过则强制停止
            use_planner: False 时跳过大脑规划，直接由小脑决策
        """
        if image_source is not None:
            BaseBrain.set_image_source(image_source)
        self.big_brain = BigBrain()
        self.small_brain = SmallBrain(backend=backend, settle_time=settle_time, interactive=interactive)
        self.max_steps = max_steps
        self.use_planner = use_planner

    def run_task_cycle(self, instruction):
        # 执行单次任务循环（串联模式）

        try:
            image_base64_1, image_base64_2 = self.small_brain.capture_pair()
        except Exception as e:
            print(f"抓图失败: {e}")
            return None, True  # 返回错误信号，停止循环
        
        # 首先调用大脑生成任务规划
        task_plan = None
        if self.use_planner:
            print("正在生成任务规划...")
            try:
                task_plan = self.big_brain.call_qvqmax_api_for_planning(image_base64_1, instruction, image_base64_2)
                self.big_brain.log_decision(task_plan)
            except Exception as e:
                print(f"请检查QVQMAX API是否正常: {e}")
                task_plan = None
        if task_plan:
            print("任务规划生成成功:")
            print(json.dumps(task_plan, indent=2, ensure_ascii=False))
        else:
            print("任务规划生成失败，将直接执行决策")
        
        # 持续执行直到任务完成
        task_completed = False
        step_count = 1
        
        actions_taken = 0
        while not task_completed:
            if actions_taken >= self.max_steps:
                print(f"已达到最大动作数 {self.max_steps}，强制停止")
                self.small_brain.backend.stop()
                return None, True
            actions_taken += 1
            print(f"\n执行步骤 {step_count}（第 {actions_taken} 个动作）")
            
            # 只调用小脑API执行决策
            decision_response = self.small_brain.call_lmstudio_api(image_base64_1, instruction, task_plan, step_count, image_base64_2)
            
            # 执行决策
            if decision_response:
                try:
                    image_base64_1, image_base64_2 = self.small_brain.execute_decision(decision_response)
                except Exception as e:
                    print(f"执行或抓图失败，停止任务: {e}")
                    self.small_brain.backend.stop()
                    return None, True
                
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
                self.small_brain.backend.stop()
                return None, True  # 返回错误信号，停止循环

    def run_task(self, instruction) -> bool:
        """执行一条指令直到模型回复"任务完成"或出错。返回是否完成。"""
        while True:
            decision_response, should_break = self.run_task_cycle(instruction)
            if should_break:
                done = bool(decision_response and decision_response.get('status') == '任务完成')
                if not done:
                    self.small_brain.backend.stop()
                return done
            time.sleep(1)

    def close(self):
        self.small_brain.backend.close()
        BaseBrain.get_image_source().close()

    def run(self):
        """运行主程序（交互式命令行）"""
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
            done = self.run_task(instruction)
            print("任务完成" if done else "任务未完成（出错或被中止）")


def main():
    controller = DualBrainController()
    try:
        controller.run()
    finally:
        controller.close()


if __name__ == "__main__":
    main()