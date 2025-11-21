import ollama
import requests
import json

def test_ollama_python_library():
    """
    测试1: 使用Ollama Python库直接与模型对话（修正版）
    """
    print("=== 测试1: 使用Ollama Python库 ===")
    try:
        # 检查本地已有哪些模型
        models_response = ollama.list()
        
        # 正确的数据结构访问方式
        if hasattr(models_response, 'models'):
            model_names = []
            for model in models_response.models:
                model_names.append(model.model)  # 使用 .model 而不是 ['name']
            
            print(f"✅ 本地已安装的模型: {model_names}")
        else:
            print("❌ 响应中未找到'models'属性")
            return False
        
        # 与qwen3:8b模型对话
        print("正在与qwen3:8b模型对话...")
        response = ollama.chat(
            model='qwen3:8b',
            messages=[
                {
                    'role': 'user',
                    'content': "请用一句话介绍你自己，并写一个简单的Python函数计算斐波那契数列。",
                }
            ],
            options={
                'temperature': 0.7,
                'num_predict': 500  # 增加长度以容纳代码
            }
        )
        print("✅ 对话成功！")
        print("Qwen3 回答:")
        print(response.message.content)  # 使用 .message.content 而不是 ['message']['content']
        print("-" * 50)
        return True
        
    except Exception as e:
        print(f"❌ Ollama Python库测试失败: {e}")
        import traceback
        print(f"详细错误信息: {traceback.format_exc()}")
        return False

def test_ollama_http_api():
    """
    测试2: 通过HTTP API直接与Ollama服务交互
    这种方式可以帮你了解API的原始格式，便于集成到其他系统。
    """
    print("\n=== 测试2: 通过HTTP API测试 ===")
    try:
        # 测试1: 检查API服务是否在线
        tags_response = requests.get('http://localhost:11434/api/tags')
        if tags_response.status_code == 200:
            print("✅ Ollama API服务连接正常")
            models = tags_response.json()
            print(f"可用模型: {[model['name'] for model in models.get('models', [])]}")
        else:
            print("❌ Ollama API服务连接失败")
            return False

        # 测试2: 发送聊天请求
        chat_data = {
            'model': 'qwen3:8b',
            'messages': [
                {
                    'role': 'user',
                    'content': "什么是机器学习？请用通俗易懂的方式解释。"
                }
            ],
            'stream': False  # 设为True可以体验流式输出（类似打字机效果）
        }
        
        chat_response = requests.post(
            'http://localhost:11434/api/chat',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(chat_data)
        )
        
        if chat_response.status_code == 200:
            result = chat_response.json()
            print("✅ HTTP API聊天测试成功")
            print("Qwen3 回答:")
            print(result['message']['content'])
        else:
            print(f"❌ HTTP API聊天测试失败，状态码: {chat_response.status_code}")
            print(f"错误信息: {chat_response.text}")
            return False
            
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到Ollama服务，请确认:")
        print("1. 已运行 'ollama serve' 启动服务")
        print("2. 服务正在 localhost:11434 上运行")
        return False
    except Exception as e:
        print(f"❌ HTTP API测试发生未知错误: {e}")
        return False

def test_reasoning_modes():
    """
    测试3: 测试Qwen3的特色功能 - 思维模式切换
    Qwen3支持通过 /think 和 /no_think 标签控制推理深度。
    """
    print("\n=== 测试3: 思维模式测试 ===")
    
    # 测试深度思考模式
    think_response = ollama.chat(
        model='qwen3:8b',
        messages=[
            {
                'role': 'user', 
                'content': "如何证明勾股定理？请详细解释每一步。 /think"
            }
        ]
    )
    print("🔍 深度思考模式回答样本:")
    print(think_response['message']['content'][:200] + "...")  # 只显示前200字符
    
    # 测试快速响应模式
    no_think_response = ollama.chat(
        model='qwen3:8b',
        messages=[
            {
                'role': 'user',
                'content': "如何证明勾股定理？ /no_think"
            }
        ]
    )
    print("\n⚡ 快速响应模式回答样本:")
    print(no_think_response['message']['content'][:200] + "...")
    
    print("✅ 思维模式测试完成（注意回答深度和细节的差异）")

def main():
    """
    主测试函数
    """
    print("开始测试本地Ollama中的Qwen3:8B模型...")
    print("确保已运行 'ollama serve' 启动本地服务\n")
    
    # 运行所有测试
    test1_success = test_ollama_python_library()
    test2_success = test_ollama_http_api()
    
    if test1_success and test2_success:
        print("\n🎉 基础测试全部通过！")
        # 可选：运行思维模式测试（可能会生成较长输出）
        run_advanced = input("\n是否运行高级思维模式测试？(y/n): ").lower().strip()
        if run_advanced == 'y':
            test_reasoning_modes()
    else:
        print("\n⚠️ 部分测试失败，请检查Ollama服务状态")
        print("故障排除步骤:")
        print("1. 在新的终端窗口中运行: ollama serve")
        print("2. 确认qwen3:8b模型已下载: ollama list")
        print("3. 如果模型不存在，运行: ollama pull qwen3:8b")
    
    print("\n测试完成！")

if __name__ == "__main__":
    main()