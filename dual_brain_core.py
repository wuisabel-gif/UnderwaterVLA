import base64
import json
import time
import os
from PIL import ImageGrab
import io
from openai import OpenAI
from QGC.rov_movement import RovMovement
ROV=RovMovement()
direction_map = {
            '前': 'forward',
            '后': 'backward',
            '左': 'left',
            '右': 'right',
            '停': 'stop'
        }
        
        # 创建速度映射字典
speed_map = {
            'low': 100,
            'medium': 200,
            'high': 300,
            'stop': 0
        }


class MPCController:
    """MPC控制器类，用于控制ROV运动"""
    
    def __init__(self, rov):
        self.rov = rov
        self.control_frequency = 1  # 1Hz控制频率
        self.total_time = 5  # 总控制时间5秒
        self.acceleration_time = self.total_time / 2  # 前2.5秒加速
        self.deceleration_time = self.total_time / 2  # 后2.5秒减速
        
    def execute_motion(self, direction, target_speed):
        """
        执行运动控制：先加速到目标速度，再减速到0
        Args:
            direction (str): 运动方向
            target_speed (int): 目标速度
        """
        print(f"MPC控制开始：方向={direction}, 目标速度={target_speed}")
        
        # 计算每个控制周期的时间间隔
        time_step = 1.0 / self.control_frequency
        
        # 加速阶段
        steps_accel = int(self.acceleration_time * self.control_frequency)
        if steps_accel > 0:
            speed_step = target_speed / steps_accel
            
            for i in range(steps_accel):
                current_speed = int((i + 1) * speed_step)
                print(f"加速阶段: 步骤 {i+1}/{steps_accel}, 速度={current_speed}")
                self.rov.move(direction, current_speed, time_step)
                time.sleep(time_step)
        
        # 减速阶段
        steps_decel = int(self.deceleration_time * self.control_frequency)
        if steps_decel > 0:
            speed_step = target_speed / steps_decel
            
            for i in range(steps_decel):
                current_speed = int(target_speed - (i + 1) * speed_step)
                # 确保速度不低于0
                current_speed = max(0, current_speed)
                print(f"减速阶段: 步骤 {i+1}/{steps_decel}, 速度={current_speed}")
                self.rov.move(direction, current_speed, time_step)
                time.sleep(time_step)
        
        # 确保最后停下來
        self.rov.move(direction, 0, time_step)
        print("MPC控制结束")
class BaseBrain:
    """基类，包含大脑和小脑的公共方法"""
    
    # 配置
    # 所有凭据与端点均从环境变量读取，避免把密钥写进代码仓库
    QVQMAX_API_URL = os.environ.get("QVQMAX_API_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QVQMAX_API_KEY = os.environ.get("QVQMAX_API_KEY", "")
    LMSTUDIO_API_URL = os.environ.get("LMSTUDIO_API_URL", "http://127.0.0.1:1234/v1")
    LMSTUDIO_API_KEY = os.environ.get("LMSTUDIO_API_KEY", "lm-studio")
    LMSTUDIO_MODEL = os.environ.get("LMSTUDIO_MODEL", "qwen2.5-vl-7b-instruct")
    
    def __init__(self):
        # 预设指令字典
        self.preset_instructions = {
            "exp1": "去最远的柱子,并且不碰到障碍物。严格按照示例中说明的JSON格式输出下一时刻的动作。",
            "exp2": "钻过呼啦圈",
            "exp3": "判断鱼的轨迹 避开鱼"
        }
    
    def encode_image_to_base64(self):
        """
        截取屏幕，顺时针旋转90度，保存为PNG文件，并返回base64编码的字符串
        返回: (base64_string, filename) 元组
        """
        # 获取当前时间作为文件名
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"FIG/{timestamp}.png"
        
        try:
            # 确保 FIG 目录存在
            os.makedirs("FIG", exist_ok=True)
            
            # 截取屏幕
            screenshot = ImageGrab.grab()
            
            # 顺时针旋转90度
            screenshot = screenshot.rotate(-90, expand=True)
            
            # 保存到磁盘
            screenshot.save(filename, format="PNG")
            
            # 同时保存到内存缓冲区用于 base64 编码
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            base64_string = base64.b64encode(image_bytes).decode('utf-8')
            
            print(f"截图成功，已旋转并保存为: {filename}")
            return base64_string, filename
            
        except Exception as e:
            print(f"截图失败: {e}")
            return None, None

    def log_decision(self, decision):
        # 将决策记录到日志中
        # 创建日志条目，包含时间戳和决策内容
        log_entry = {
            "timestamp": time.time(),
            "decision": decision
        }
        # 将日志条目追加到文件中
        try:
            with open("decision_log.json", "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"写入决策日志时出错: {e}")



class BigBrain(BaseBrain):
    """大脑类，负责任务规划"""
    
    def call_qvqmax_api_for_planning(self, image_base64, instruction, image_base64_2=None):
        # 调用QVQmax云端大脑API生成任务规划
        #
        # Args:
        #     image_base64 (str): 第一张图片的base64编码
        #     instruction (str): 指令文本
        #     image_base64_2 (str, optional): 第二张图片的base64编码，默认为None
        #
        # Returns:
        #     dict or None: API响应解析后的JSON对象，失败时返回None
        reasoning_content = ""  # 定义完整思考过程
        answer_content = ""     # 定义完整回复
        is_answering = False   # 判断是否结束思考过程并开始回复
        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=self.QVQMAX_API_KEY,
            base_url=self.QVQMAX_API_URL
        )
        
        # 构建用户内容，支持一张或两张图片
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        # 如果提供了第二张图片，也添加到内容中
        if image_base64_2:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64_2}"
                }
            })
        
        # 添加指令文本
        user_content.append({
            "type": "text",
            "text": instruction
        })
        
        # 为大脑规划创建系统提示
        planning_system_prompt = {
            "role": "underwater_robot_task_planner",
            "description": "你是一个面向水下场景的任务规划专家，需要基于图像和指令生成多个步骤的详细的任务执行计划。",
            "rules": [
                "仔细分析图像中的环境和障碍物",
                "根据用户指令制定分多个步骤的执行计划",
                "每个步骤应该明确具体的操作和目标",
                "计划应该考虑安全性和效率",
                "以标准JSON格式输出结果"
            ],
            "input_format": {
                "image": "base64 encoded JPEG image (single or multiple views)",
                "instruction": "string"
            },
            "output_format": {
                "reasoning":"string (对任务的分析理解思考过程)",
                "task_plan": [
                    {
                        "step": "integer (步骤编号)",
                        "description": "string (对该步骤的详细描述)",
                        "target_object": "string (目标对象)",
                        "obstacle_to_avoid": "string (需要避开的障碍物)",
                        "confidence": "float [0.0-1.0] (规划的置信度)"
                    }
                ],
                "total_steps": "integer (总步骤大于1)",
                "estimated_completion_time": "string (预估完成时间)"
            }
        }

        messages = [
            {
                "role": "system",
                "content": json.dumps(planning_system_prompt, ensure_ascii=False)
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        

        # 创建聊天完成请求
        completion = client.chat.completions.create(
            model="qwen-vl-max-latest",
            messages=messages,
            stream=True,
            temperature=0.9,  # 适度的创造性
            max_tokens=800,   # 允许更长的规划描述
        )
        
        # 获取响应内容
            # 获取响应内容
        for chunk in completion:
            # 如果chunk.choices为空，则打印usage
            if not chunk.choices:
                print("\nUsage:")
                print(chunk.usage)
            else:
                delta = chunk.choices[0].delta
                # 打印思考过程
                if hasattr(delta, 'reasoning_content') and delta.reasoning_content != None:
                    print(delta.reasoning_content, end='', flush=True)
                    reasoning_content += delta.reasoning_content
                else:
                    # 开始回复
                    if delta.content != "" and is_answering is False:
                        print("\n" + "=" * 20 + "完整回复" + "=" * 20 + "\n")
                        is_answering = True
                    # 打印回复过程
                    print(delta.content, end='', flush=True)
                    answer_content += delta.content


        if answer_content:
            try:
                # 清理可能的markdown代码块包装
                cleaned_output = answer_content.strip()
                if cleaned_output.startswith("```json"):
                    # 去掉开头的 ```json 和结尾的 ```
                    cleaned_output = cleaned_output[7:].strip()
                    if cleaned_output.endswith("```"):
                        cleaned_output = cleaned_output[:-3].strip()
                elif cleaned_output.startswith("```"):
                    # 去掉开头的 ``` 和结尾的 ```
                    cleaned_output = cleaned_output[3:].strip()
                    if cleaned_output.endswith("```"):
                        cleaned_output = cleaned_output[:-3].strip()
                return json.loads(cleaned_output)
            except json.JSONDecodeError:
                print(f"QVQmax Planning API returned invalid JSON: {answer_content}")
                return None
        else:
            print("QVQmax Planning API returned empty output")
            return None


class SmallBrain(BaseBrain):
    """小脑类，负责执行决策"""
    
    def __init__(self):
        super().__init__()
        # 初始化MPC控制器
        self.mpc_controller = MPCController(ROV)
    
    def call_lmstudio_api(self, image_base64, instruction, task_plan=None, current_step=None, image_base64_2=None):
        # 调用LM Studio本地小脑API
        #
        # Args:
        #     image_base64 (str): 第一张图片的base64编码
        #     instruction (str): 指令文本
        #     task_plan (dict, optional): 大脑生成的任务规划
        #     current_step (int, optional): 当前执行步骤
        #     image_base64_2 (str, optional): 第二张图片的base64编码，默认为None
        #
        # Returns:
        #     dict or None: API响应解析后的JSON对象，失败时返回None
        
        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=self.LMSTUDIO_API_KEY,
            base_url=self.LMSTUDIO_API_URL
        )
        
        # 构建用户内容，支持一张或两张图片
        user_content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            }
        ]
        
        # 如果提供了第二张图片，也添加到内容中
        if image_base64_2:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64_2}"
                }
            })
        
        # 添加指令文本和任务规划（如果有的话）
        text_content = f"指令: {instruction}"
        if task_plan and current_step is not None:
            text_content += f"\n任务规划: {json.dumps(task_plan, ensure_ascii=False)}"
            text_content += f"\n当前步骤: {current_step}"
            
        user_content.append({
            "type": "text",
            "text": text_content
        })
        
        # 为小脑决策创建系统提示
        decision_system_prompt = {
            "role": "underwater_robot_vla_navigator",
            "description": "你是一个面向水下场景的纯视觉-语言-动作（VLA）决策模型，基于实时图像分析和自然语言指令生成运动指令并且回忆上下文图片时间序列做决策。请严格遵循以下规则：",
            "rules": [
                "仅接收单目RGB图像作为视觉输入",
                "必须结合用户指令理解任务目标",
                "如果有任务规划，需要按照当前步骤执行，如果你判断上一个步骤尚未完成请按照上一个步骤执行，在输出中添加step_completed: true字段",
                "每次决策必须从[前, 后, 左, 右, 停,]五个基础动作中选择",
                "每次决策必须从['low','medium','high','stop']五个基础速度中选择",
                "严格以标准JSON格式输出结果，禁止任何额外文本",
                "你认为未完成任务的时候选择输出任务中，完成任务的时候选择输出任务完成并且停止",
            ],
            "input_format": {
                "image": "base64 encoded JPEG image (single or multiple views)",
                "instruction": "string",
                "task_plan": "optional task plan from brain",
                "current_step": "optional current step number"
            },
            "output_format": {
                "reasoning": "string(对这个图片的思考和做决策的原因)",
                "action": {
                    "direction": "string (enum: ['前','后','左','右','停'])",
                    "speed": "string (enum: ['low','medium','high','stop'])",
                    "confidence": "float [0.0-1.0]"
                },
                "status": "string (enum: ['任务中', '任务完成'])",
                "step_completed": "boolean (可选，步骤是否完成)"
            }
        }
        
        messages = [
            {
                "role": "system",
                "content": json.dumps(decision_system_prompt, ensure_ascii=False)
            },
            {
                "role": "user",
                "content": user_content
            }
        ]
        
        try:
            # 创建聊天完成请求
            completion = client.chat.completions.create(
                model=self.LMSTUDIO_MODEL,
                messages=messages,
                stream=False,
                temperature=0.5,  # 设置温度为0以获得确定性输出
                max_tokens=500,
            )
            
            # 获取响应内容
            response_content = completion.choices[0].message.content if completion.choices else None
            if response_content:
                try:
                    # 清理可能的markdown代码块包装
                    cleaned_output = response_content.strip()
                    if cleaned_output.startswith("```json"):
                        # 去掉开头的 ```json 和结尾的 ```
                        cleaned_output = cleaned_output[7:].strip()
                        if cleaned_output.endswith("```"):
                            cleaned_output = cleaned_output[:-3].strip()
                    elif cleaned_output.startswith("```"):
                        # 去掉开头的 ``` 和结尾的 ```
                        cleaned_output = cleaned_output[3:].strip()
                        if cleaned_output.endswith("```"):
                            cleaned_output = cleaned_output[:-3].strip()
                    return json.loads(cleaned_output)
                except json.JSONDecodeError:
                    print(f"LM Studio API returned invalid JSON: {response_content}")
                    return None
            else:
                print("LM Studio API returned empty output")
                return None
                
        except Exception as e:
            print(f"Error calling LM Studio API: {e}")
            return None

    def execute_decision(self, decision):
        # 执行决策（此处为打印，实际应用中应控制机器人）
        # 将决策添加到日志中
        self.log_decision(decision)
        print("执行决策:")
        print(json.dumps(decision, indent=2, ensure_ascii=False))
        action = decision.get('action', {})
        direction = action.get('direction')
        speed = action.get('speed')

        # 使用MPC控制器执行运动控制
        mapped_direction = direction_map.get(direction, direction)
        mapped_speed = speed_map.get(speed, speed)
        
        # MPC控制器将在5秒内执行：先加速到目标速度，再减速到0
        self.mpc_controller.execute_motion(mapped_direction, mapped_speed)

        print("是否执行完毕")
        user_input = input().strip()
        print(f"5s秒后screenshot")
        time.sleep(5)
        # 编码图片为base64
        while 1:
            try:
                image_base64_1 = self.encode_image_to_base64()
                time.sleep(1)
                image_base64_2 = self.encode_image_to_base64()
                break
            except Exception as e:
                print(f"Error encoding images: {e}")
                # 如果无法读取新图片，则使用原图片

        # 返回编码后的图片数据，供后续使用
        return image_base64_1, image_base64_2
