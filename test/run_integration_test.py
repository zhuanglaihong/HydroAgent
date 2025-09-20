#!/usr/bin/env python3
"""
简化的集成测试运行脚本
快速测试完整系统流程
"""

import asyncio
import sys
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_ollama():
    """设置Ollama客户端"""
    try:
        import ollama
        client = ollama.Client()
        
        # 测试连接和模型
        logger.info("检查Ollama连接...")
        
        # 测试qwen3:8b模型
        response = client.chat(
            model="qwen3:8b",
            messages=[{"role": "user", "content": "test connection"}]
        )
        logger.info("✅ qwen3:8b模型可用")
        
        # 测试bge-large:335m嵌入模型
        embeddings = client.embeddings(
            model="bge-large:335m",
            prompt="test embeddings"
        )
        logger.info("✅ bge-large:335m模型可用")
        
        return client
        
    except ImportError:
        logger.error("❌ ollama库未安装，请先安装: pip install ollama")
        return None
    except Exception as e:
        logger.error(f"❌ Ollama连接失败: {e}")
        logger.error("请确保Ollama服务已启动且所需模型已下载:")
        logger.error("1. ollama serve")
        logger.error("2. ollama pull qwen3:8b")
        logger.error("3. ollama pull bge-large:335m")
        return None

async def run_test():
    """运行集成测试"""
    from test_complete_workflow_integration import main
    
    print("🚀 启动HydroAgent完整系统集成测试")
    print("测试场景：整理数据camels_11532500流域，用其率定GR4J模型，并评估模型")
    print("=" * 70)
    
    # 1. 设置Ollama客户端
    ollama_client = setup_ollama()
    if not ollama_client:
        print("❌ Ollama设置失败，无法继续测试")
        return False
    
    # 2. 运行测试
    try:
        await main(ollama_client=ollama_client)
        return True
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        return False
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
