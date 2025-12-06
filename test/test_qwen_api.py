import os
from openai import OpenAI

# 1. 设置API Key（请先设置环境变量QWEN_API_KEY，或直接在此替换）
api_key = "sk-50be7aaa64564360bb2a6dbd2e2db325"
if not api_key:
    # 如果未设置环境变量，可以在此直接替换（注意：不推荐在生产环境中硬编码密钥）
    # api_key = "sk-你的实际API-KEY"
    raise ValueError("请设置环境变量 QWEN_API_KEY")

# 2. 初始化客户端
client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"  # 阿里云Qwen服务的兼容端点
)

def ask_qwen(question, model="qwen-flash", temperature=0.8):
    """
    向Qwen模型提问并获取回答
    """
    try:
        # 3. 调用API
        completion = client.chat.completions.create(
            model=model,           # 可选模型：qwen-turbo, qwen-plus, qwen-max等[1,7](@ref)
            messages=[
                {"role": "system", "content": "你是一个有用的AI助手。"},  # 系统提示词，定义助手角色
                {"role": "user", "content": question}                   # 用户问题
            ],
            temperature=temperature,  # 控制回答随机性（0.0-1.0），值越高回答越具创造性
            max_tokens=1500           # 限制生成回答的最大长度
        )
        # 4. 提取并返回回答
        return completion.choices[0].message.content
    except Exception as e:
        return f"调用API时出错: {e}"

# 5. 测试脚本
if __name__ == "__main__":
    # 测试问题
    test_questions = [
        "你好，请简单介绍一下你自己。",
        "用Python写一个计算斐波那契数列的函数。",
        "解释一下什么是机器学习。"
    ]
    
    print("=== 通义千问API测试开始 ===\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"问题 {i}: {question}")
        print("--- Qwen回答 ---")
        answer = ask_qwen(question)
        print(answer)
        print("\n" + "="*50 + "\n")