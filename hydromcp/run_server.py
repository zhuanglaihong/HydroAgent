"""
启动MCP服务器的辅助脚本
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根路径
repo_path = Path(os.path.abspath(__file__)).parent.parent
sys.path.append(str(repo_path))

from hydromcp.server import hydro_mcp_server

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("mcp_server.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)

def print_banner():
    """打印欢迎横幅"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    水文模型MCP服务器                          ║
║                 Hydro Model MCP Server                       ║
║                                                              ║
║  🔧 提供水文模型工具服务                                      ║
║  🚀 支持远程工具调用                                          ║
║  ⚡ 高效的进程间通信                                          ║
╚══════════════════════════════════════════════════════════════╝
    """)

async def main():
    """主函数"""
    print_banner()
    
    try:
        # 设置工作目录
        os.chdir(repo_path)
        logger.info(f"工作目录: {repo_path}")
        
        # 启动服务器
        logger.info("正在启动MCP服务器...")
        await hydro_mcp_server.start()
        
    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在停止服务器...")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
