r"""
Author: Claude Code
Date: 2025-10-12 16:15:00
LastEditTime: 2025-10-12 16:15:00
LastEditors: Claude Code
Description: 检查Ollama服务和嵌入模型状态
FilePath: \HydroAgent\script\check_ollama_status.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import sys
from pathlib import Path
import time
import gc
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_embedding_with_timeout(test_model, timeout=10):
    """
    在独立线程中测试嵌入模型，带超时保护

    Args:
        test_model: 模型名称
        timeout: 超时时间（秒）

    Returns:
        tuple: (success, message, details)
    """
    def _do_test():
        try:
            # 导入必要的库
            try:
                from langchain_ollama import OllamaEmbeddings
                lib_name = "langchain_ollama"
            except ImportError:
                from langchain_community.embeddings import OllamaEmbeddings
                lib_name = "langchain_community"

            # 创建嵌入模型
            embeddings = OllamaEmbeddings(
                model=test_model,
                base_url="http://localhost:11434"
            )

            # 单次嵌入测试
            test_text = "这是一个测试文本"
            start_time = time.time()
            embedding = embeddings.embed_query(test_text)
            single_elapsed = time.time() - start_time

            if not embedding or len(embedding) == 0:
                return (False, "嵌入向量为空", {})

            # 批量嵌入测试
            start_time = time.time()
            batch_embeddings = embeddings.embed_documents([
                "文本1", "文本2", "文本3"
            ])
            batch_elapsed = time.time() - start_time

            # 清理资源
            try:
                if hasattr(embeddings, 'client'):
                    if hasattr(embeddings.client, 'close'):
                        embeddings.client.close()
                    # 额外尝试：httpx 客户端清理
                    if hasattr(embeddings.client, 'aclose'):
                        import asyncio
                        try:
                            asyncio.get_event_loop().run_until_complete(embeddings.client.aclose())
                        except:
                            pass
                del embeddings
            except:
                pass

            details = {
                "lib": lib_name,
                "dimension": len(embedding),
                "single_time": single_elapsed,
                "batch_time": batch_elapsed,
                "batch_count": len(batch_embeddings),
                "sample": embedding[:5]
            }

            return (True, "测试成功", details)

        except Exception as e:
            return (False, f"测试失败: {str(e)}", {})

    # 在线程池中执行测试，带超时
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_do_test)
        try:
            result = future.result(timeout=timeout)
            # 强制垃圾回收
            gc.collect()
            return result
        except FutureTimeoutError:
            return (False, f"测试超时（{timeout}秒）", {})
        except Exception as e:
            return (False, f"执行异常: {str(e)}", {})

def check_ollama_service():
    """检查Ollama服务状态"""
    print("=" * 80)
    print("检查Ollama服务状态")
    print("=" * 80)

    import requests

    print("\n1. 检查Ollama服务连接...")
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)

        if response.status_code == 200:
            print("   ✓ Ollama服务正常运行")

            data = response.json()
            models = data.get("models", [])

            print(f"\n2. 可用模型列表 ({len(models)} 个):")
            for model in models:
                name = model.get("name", "Unknown")
                size = model.get("size", 0) / (1024**3)  # 转换为GB
                print(f"   - {name} ({size:.2f} GB)")

            # 检查嵌入模型
            print("\n3. 检查嵌入模型...")
            embed_keywords = ["embed", "bge", "nomic", "gte", "sentence"]
            embed_models = [
                m["name"] for m in models
                if any(kw in m["name"].lower() for kw in embed_keywords)
            ]

            if embed_models:
                print(f"   ✓ 找到 {len(embed_models)} 个嵌入模型:")
                for model in embed_models:
                    print(f"     - {model}")
            else:
                print("   ✗ 没有找到嵌入模型!")
                print("\n   建议安装一个嵌入模型:")
                print("   ollama pull bge-large:335m")
                print("   或")
                print("   ollama pull nomic-embed-text")
                return False

            # 测试嵌入模型
            print("\n4. 测试嵌入模型...")
            test_model = embed_models[0]
            print(f"   使用模型: {test_model}")
            print("   正在测试嵌入功能（带超时保护）...")

            # 使用带超时保护的测试函数
            success, message, details = test_embedding_with_timeout(test_model, timeout=15)

            if success:
                print(f"   [OK] {message}")
                print(f"     - 使用库: {details.get('lib', 'N/A')}")
                print(f"     - 维度: {details.get('dimension', 0)}")
                print(f"     - 单次耗时: {details.get('single_time', 0):.2f} 秒")
                print(f"     - 批量耗时: {details.get('batch_time', 0):.2f} 秒 ({details.get('batch_count', 0)} 个)")
                print(f"     - 样本值: {details.get('sample', [])}")
                print("   [OK] 资源已自动清理")
                return True
            else:
                print(f"   [ERROR] {message}")
                print("\n   可能的原因:")
                print("   1. 模型正在加载中（首次使用需要时间）")
                print("   2. Ollama服务响应慢或卡住")
                print("   3. 系统内存不足")
                print("   4. HTTP连接池未正确释放（重启Ollama服务试试）")
                return False

        else:
            print(f"   ✗ Ollama服务响应异常: HTTP {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("   ✗ 无法连接到Ollama服务!")
        print("\n   请检查:")
        print("   1. Ollama是否已安装? 访问 https://ollama.ai/")
        print("   2. Ollama服务是否运行? 运行命令: ollama serve")
        print("   3. 端口11434是否被占用?")
        return False

    except requests.exceptions.Timeout:
        print("   ✗ 连接Ollama服务超时!")
        return False

    except Exception as e:
        print(f"   ✗ 检查失败: {e}")
        return False

def main():
    result = check_ollama_service()

    print("\n" + "=" * 80)
    if result:
        print("状态: ✓ 所有检查通过，可以运行RAG重建脚本")
        print("\n下一步:")
        print("  python script/quick_rag_rebuild.py")
    else:
        print("状态: ✗ 检查失败，请修复上述问题后重试")
        print("\n常见问题解决:")
        print("  1. 启动Ollama: ollama serve")
        print("  2. 安装嵌入模型: ollama pull bge-large:335m")
        print("  3. 检查安装: ollama list")
    print("=" * 80)

if __name__ == "__main__":
    main()
