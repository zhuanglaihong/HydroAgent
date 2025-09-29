"""
Author: zhuanglaihong
Date: 2024-09-24 16:52:00
LastEditTime: 2024-09-24 16:52:00
LastEditors: zhuanglaihong
Description: API client wrapper for external API services
FilePath: \HydroAgent\builder\api_client.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import logging

logger = logging.getLogger(__name__)


def get_api_response(
    prompt: str, model: str = "qwen-turbo", temperature: float = 0.8
) -> str:
    """
    调用外部API获取响应

    Args:
        prompt: 输入提示词
        model: 模型名称
        temperature: 温度参数

    Returns:
        str: API响应内容，失败返回None
    """
    try:
        # 动态导入避免初始化问题
        from openai import OpenAI
        import os

        # 尝试从definitions导入API Key
        try:
            from definitions import OPENAI_API_KEY

            api_key = OPENAI_API_KEY
        except ImportError:
            # 如果导入失败，尝试从环境变量获取
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            logger.warning("API Key不可用")
            return None

        # 创建客户端
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 调用API
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )

        return completion.choices[0].message.content

    except Exception as e:
        logger.error(f"API调用失败: {str(e)}")
        return None
