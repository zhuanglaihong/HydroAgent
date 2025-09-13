"""
Author: zhuanglaihong
Date: 2025-07-28 16:24:08
LastEditTime: 2025-07-28 16:24:08
Description: 智能体主界面 - 用户调用本地Ollama模型配合水文工具进行自动率定
FilePath: script/Agent.py
Copyright: Copyright (c) 2021-2024 zhuanglaihong. All rights reserved.
"""

import sys
import os
from pathlib import Path
import argparse
import json
from typing import Dict, Any, Optional

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from tool.ollama_config import ollama_config, create_tool_supported_llm
from tool.langchain_agent import create_hydromodel_agent
from tool.langchain_tool import get_hydromodel_tools
from definitions import DATASET_DIR, RESULT_DIR


class HydroModelAgent:
    """水文模型智能体"""

    def __init__(self, model_name: Optional[str] = None):
        """
        初始化智能体

        Args:
            model_name: 指定的模型名称，如果为None则自动选择
        """
        self.model_name = model_name
        self.agent = None
        self.tools = []
        self.session_history = []

        # 初始化智能体
        self._initialize_agent()

    def _initialize_agent(self):
        """初始化智能体和工具"""
        print("🚀 正在初始化水文模型智能体...")

        # 检查 Ollama 服务
        if not ollama_config.check_service():
            raise RuntimeError("❌ Ollama 服务未运行，请先启动 Ollama 服务")

        print("✅ Ollama 服务运行正常")

        # 获取可用模型
        available_models = ollama_config.get_available_models()
        if not available_models:
            raise RuntimeError("❌ 没有找到可用的模型")

        print(f"📋 可用模型: {', '.join(available_models)}")

        # 选择模型
        if self.model_name:
            if self.model_name not in available_models:
                print(f"❌ 指定模型 {self.model_name} 不可用")
                print(f"💡 可用模型: {', '.join(available_models)}")
                raise ValueError(f"模型 {self.model_name} 不可用")
            selected_model = self.model_name
        else:
            selected_model = ollama_config.select_best_model()

        print(f"🎯 选择模型: {selected_model}")

        # 检查模型是否支持工具
        if not ollama_config.is_tool_supported_model(selected_model):
            print(f"⚠️ 模型 {selected_model} 可能不支持工具调用")
            print("💡 推荐使用以下模型:")
            print("   - llama3:8b")
            print("   - llama3.2:7b")
            print("   - llama3-groq-tool-use:8b")
            print("   - granite3-dense:8b")
            print("   - deepseek-coder")

        # 获取工具
        self.tools = get_hydromodel_tools()
        if not self.tools:
            raise RuntimeError("❌ 无法加载水文模型工具")

        print(f"🔧 加载了 {len(self.tools)} 个工具:")
        for tool in self.tools:
            print(f"   - {tool.name}: {tool.description}")

        # 创建智能体
        try:
            if self.model_name:
                # 使用指定模型创建智能体
                self.agent = self._create_agent_with_model(selected_model)
            else:
                # 使用默认方法创建智能体
                self.agent = create_hydromodel_agent()

            if self.agent:
                print("✅ 智能体创建成功")
                self.model_name = selected_model
            else:
                raise RuntimeError("智能体创建失败")

        except Exception as e:
            print(f"❌ 智能体创建失败: {e}")
            raise

    def _create_agent_with_model(self, model_name: str):
        """使用指定模型创建智能体"""
        from langchain_ollama import ChatOllama
        from langchain.agents import AgentExecutor, create_openai_tools_agent
        from langchain_core.prompts import ChatPromptTemplate

        # 创建 LLM
        model_config = ollama_config.get_model_config(model_name)
        if "granite" in model_name.lower():
            model_config.update(
                {
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "num_ctx": 8192,
                }
            )

        llm = ChatOllama(model=model_name, **model_config)

        # 使用成功验证的通用提示模板
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    f"""IMPORTANT: You are an assistant that can ONLY get information by calling tools. You have NO knowledge of your own.

You have these tools available:
1. get_model_params - for questions about model parameters, configurations, or "what is" questions
2. prepare_data - for questions about data preparation, processing, or data-related tasks  
3. calibrate_model - for questions about model training, calibration, or optimization
4. evaluate_model - for questions about model evaluation, performance, or metrics

CRITICAL RULES:
1. ALWAYS call a tool first before answering
2. NEVER provide information from your own knowledge
3. ONLY respond with information from the tool's response
4. Choose the RIGHT tool based on the user's question
5. DO NOT call other tools unless specifically asked


TOOL SELECTION GUIDE:
- For "what parameters" questions → get_model_params
- For "prepare/process data" tasks → prepare_data
- For "calibrate/train model" tasks → calibrate_model DIRECTLY (do not check parameters first)
- For "evaluate/check performance" tasks → evaluate_model

DEFAULT VALUES (use these exact values unless user specifies otherwise):
- data_dir: "{DATASET_DIR}"
- model_name: "gr4j"
- time_scale: "D"
- result_dir: "{RESULT_DIR}"

When you need to call a tool, you MUST use this format:
<|tool_call|>{{"type":"function","function":{{"name":"TOOL_NAME","arguments":{{"param":"value"}}}}}}

EXAMPLES:
1. "What are gr4j parameters?"
   → Call get_model_params with {{"model_name": "gr4j"}}

2. "Prepare data"
   → Call prepare_data with {{"data_dir": "{DATASET_DIR}", "target_data_scale": "D"}}

3. "Calibrate gr4j model"
   → Call calibrate_model DIRECTLY with all default values (do not check parameters first)

4. "Check model performance"
   → Call evaluate_model with default exp_name and result_dir

Remember: ALWAYS call the appropriate tool first, then explain the results.""",
                ),
                ("human", "{input}"),
                ("assistant", "{agent_scratchpad}"),
            ]
        )

        # 创建代理
        agent = create_openai_tools_agent(llm, self.tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=6,  # 增加迭代次数用于复杂任务和完整的工具调用流程
            return_intermediate_steps=True,
            early_stopping_method="force",  # 确保完成完整流程
        )

        return agent_executor

    def chat(self, message: str) -> Dict[str, Any]:
        """
        与智能体对话

        Args:
            message: 用户消息

        Returns:
            包含回复和元数据的字典
        """
        if not self.agent:
            raise RuntimeError("智能体未初始化")

        print(f"\n👤 用户: {message}")
        print("🤔 智能体正在思考...")

        try:
            # 调用智能体
            response = self.agent.invoke({"input": message})

            # 记录会话历史
            self.session_history.append(
                {
                    "user": message,
                    "assistant": response["output"],
                    "intermediate_steps": response.get("intermediate_steps", []),
                }
            )

            print(f"\n🤖 智能体: {response['output']}")

            # 显示中间步骤（调试信息）
            if response.get("intermediate_steps"):
                print(f"\n🔧 执行了 {len(response['intermediate_steps'])} 个工具调用:")
                for i, step in enumerate(response["intermediate_steps"], 1):
                    action, result = step
                    print(f"   {i}. {action.tool}: {action.tool_input}")
                    print(f"      结果: {str(result)[:100]}...")

            return response

        except Exception as e:
            error_msg = f"❌ 对话失败: {e}"
            print(error_msg)
            return {"output": error_msg, "error": str(e)}

    def auto_calibrate(
        self, model_type: str, data_path: str, **kwargs
    ) -> Dict[str, Any]:
        """
        自动率定模型

        Args:
            model_type: 模型类型 (如 'gr4j', 'xaj' 等)
            data_path: 数据路径
            **kwargs: 其他参数

        Returns:
            率定结果
        """
        print(f"\n🎯 开始自动率定任务:")
        print(f"   模型类型: {model_type}")
        print(f"   数据路径: {data_path}")

        # 构建自动率定提示
        calibration_prompt = f"""
        请帮我进行 {model_type} 模型的自动率定：
        
        1. 数据路径: {data_path}
        2. 模型类型: {model_type}
        
        请按照以下步骤操作：
        1. 首先使用 get_model_params 工具查看 {model_type} 模型的参数信息
        2. 使用 prepare_data 工具准备数据
        3. 使用 calibrate_model 工具进行模型率定
        4. 使用 evaluate_model 工具评估率定结果
        5. 提供详细的结果分析和建议
        
        额外参数: {json.dumps(kwargs, ensure_ascii=False, indent=2)}
        """

        # 执行自动率定
        return self.chat(calibration_prompt)

    def get_model_info(self) -> Dict[str, Any]:
        """获取当前模型信息"""
        return {
            "model_name": self.model_name,
            "tools_count": len(self.tools),
            "tools": [
                {"name": tool.name, "description": tool.description}
                for tool in self.tools
            ],
            "session_count": len(self.session_history),
        }

    def save_session(self, filepath: str):
        """保存会话历史"""
        session_data = {
            "model_name": self.model_name,
            "timestamp": str(Path().cwd()),
            "history": self.session_history,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)

        print(f"📄 会话已保存到: {filepath}")


def print_banner():
    """打印欢迎横幅"""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                    水文模型智能体系统                          ║
║                   Hydrological Model Agent                   ║
║                                                              ║
║  🤖 支持本地 Ollama 模型                                      ║
║  🔧 集成专业水文工具                                          ║
║  ⚡ 自动模型率定                                              ║
║  📊 智能结果分析                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    )


def interactive_mode(agent: HydroModelAgent):
    """交互模式"""
    print("\n🎯 进入交互模式 (输入 'quit' 或 'exit' 退出)")
    print("💡 可用命令:")
    print("   - 'info': 查看模型信息")
    print("   - 'save <filename>': 保存会话历史")
    print("   - 'auto <model_type> <data_path>': 自动率定")
    print("   - 直接输入问题进行对话")

    while True:
        try:
            user_input = input("\n👤 您: ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 再见！")
                break
            elif user_input.lower() == "info":
                info = agent.get_model_info()
                print(f"\n📊 模型信息:")
                print(f"   模型: {info['model_name']}")
                print(f"   工具数量: {info['tools_count']}")
                print(f"   会话数量: {info['session_count']}")
            elif user_input.lower().startswith("save "):
                filename = user_input[5:].strip()
                if not filename:
                    filename = (
                        f"session_{agent.model_name}_{len(agent.session_history)}.json"
                    )
                agent.save_session(filename)
            elif user_input.lower().startswith("auto "):
                parts = user_input[5:].strip().split()
                if len(parts) >= 2:
                    model_type, data_path = parts[0], parts[1]
                    agent.auto_calibrate(model_type, data_path)
                else:
                    print("❌ 用法: auto <model_type> <data_path>")
            elif user_input:
                agent.chat(user_input)

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="水文模型智能体系统")
    parser.add_argument("--model", "-m", type=str, help="指定使用的模型名称")
    parser.add_argument("--interactive", "-i", action="store_true", help="交互模式")
    parser.add_argument(
        "--auto",
        "-a",
        nargs=2,
        metavar=("MODEL_TYPE", "DATA_PATH"),
        help="自动率定模式: MODEL_TYPE DATA_PATH",
    )
    parser.add_argument("--message", type=str, help="直接发送消息")

    args = parser.parse_args()

    print_banner()

    try:
        # 创建智能体
        print("🚀 正在启动智能体...")
        agent = HydroModelAgent(model_name=args.model)

        # 显示模型信息
        info = agent.get_model_info()
        print(f"\n📊 智能体信息:")
        print(f"   🤖 模型: {info['model_name']}")
        print(f"   🔧 工具: {info['tools_count']} 个")
        for tool in info["tools"]:
            print(f"      - {tool['name']}: {tool['description']}")

        # 根据参数执行不同模式
        if args.auto:
            # 自动率定模式
            model_type, data_path = args.auto
            print(f"\n🎯 自动率定模式")
            agent.auto_calibrate(model_type, data_path)
        elif args.message:
            # 单次对话模式
            agent.chat(args.message)
        elif args.interactive:
            # 交互模式
            interactive_mode(agent)
        else:
            # 默认进入交互模式
            interactive_mode(agent)

    except Exception as e:
        print(f"❌ 智能体启动失败: {e}")
        print("\n💡 常见解决方案:")
        print("1. 检查 Ollama 服务是否运行: ollama serve")
        print("2. 检查是否安装了支持工具的模型:")
        print("   ollama pull llama3:8b")
        print("   ollama pull granite3-dense:8b")
        print("   ollama pull llama3-groq-tool-use:8b")
        print("3. 检查水文模型模块是否正确安装")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
