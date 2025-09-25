from openai import OpenAI
import os
from definitions import PROJECT_DIR, RESULT_DIR, DATASET_DIR, OPENAI_API_KEY
import numpy as np

# 设置您的 API Key
api_key = OPENAI_API_KEY
if not api_key:
    raise ValueError("请设置 QWEN_API_KEY 环境变量")

# 创建 OpenAI 客户端实例
client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

def get_qwen_response(prompt, model="qwen-turbo", temperature=0.8):
    """调用推理模型获取文本响应"""
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"调用推理模型失败: {e}")
        return None

def get_qwen_embedding(text, model="text-embedding-v1"):
    """获取文本的嵌入向量"""
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"调用嵌入模型失败: {e}")
        return None

def get_qwen_code(prompt, model="qwen3-coder-plus", temperature=0.2):
    """调用代码生成模型获取代码"""
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"调用代码生成模型失败: {e}")
        return None

# ========== 使用示例 ==========

# 1. 使用推理模型（通用对话）
print("===== 推理模型示例 =====")
response = get_qwen_response("量子计算的基本原理是什么？", model="qwen-max")
print(response[:200] + "...")  # 打印前200个字符

# 2. 使用嵌入模型（文本向量化）
print("\n===== 嵌入模型示例 =====")
embedding = get_qwen_embedding("自然语言处理技术")
if embedding:
    print(f"嵌入向量维度: {len(embedding)}")
    print(f"前5个值: {embedding[:5]}")

# 3. 使用代码生成模型
print("\n===== 代码生成模型示例 =====")
code_prompt = """
用Python实现一个函数，要求：
1. 函数名为 calculate_circle_area
2. 接收一个参数 radius（半径）
3. 返回圆的面积
4. 包含类型注解和文档字符串
"""
code = get_qwen_code(code_prompt, model="qwen3-coder-plus")
print(code)

# 4. 多模型协同工作示例
print("\n===== 多模型协同示例 =====")
# 使用推理模型生成问题
question = "生成一个关于Python列表操作的问题"
generated_question = get_qwen_response(question, model="qwen-turbo")

# 使用代码模型生成解决方案
if generated_question:
    print(f"生成的问题: {generated_question}")
    solution = get_qwen_code(f"解决以下Python问题:\n{generated_question}")
    if solution:
        print("\n生成的解决方案:")
        print(solution)
        
        # 使用嵌入模型分析代码相似度
        original_embedding = get_qwen_embedding("Python列表操作")
        solution_embedding = get_qwen_embedding(solution)
        
        if original_embedding and solution_embedding:
            # 计算余弦相似度
            dot_product = np.dot(original_embedding, solution_embedding)
            norm_orig = np.linalg.norm(original_embedding)
            norm_sol = np.linalg.norm(solution_embedding)
            similarity = dot_product / (norm_orig * norm_sol)
            print(f"\n代码与主题相似度: {similarity:.4f}")