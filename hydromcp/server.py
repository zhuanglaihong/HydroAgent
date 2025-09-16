"""
水文模型MCP服务端
用于将水文模型工具暴露为MCP服务，供Ollama等LLM使用
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Sequence
from pathlib import Path

# FastMCP相关导入
try:
    from fastmcp import FastMCP
    from mcp.types import TextContent, Tool
    MCP_AVAILABLE = True
except ImportError:
    # 如果没有安装fastmcp，提供兼容的基础类
    print("FastMCP库未安装，使用兼容模式")
    MCP_AVAILABLE = False

from .tools import HydroModelMCPTools
from .schemas import TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class HydroMCPServer:
    """水文模型MCP服务器"""
    
    def __init__(self, name: str = "hydro-model-mcp", version: str = "1.0.0"):
        """
        初始化MCP服务器
        
        Args:
            name: 服务器名称
            version: 服务器版本
        """
        self.name = name
        self.version = version
        self.tools = HydroModelMCPTools()
        
        if MCP_AVAILABLE:
            self.mcp = FastMCP(name)
            self._setup_tools()
        else:
            self.mcp = None
            logger.warning("FastMCP库不可用，无法启动MCP服务器")
    
    def _setup_tools(self):
        """注册MCP工具"""
        if not self.mcp:
            return
            
        # 注册所有工具
        for tool_name, schema in TOOL_SCHEMAS.items():
            # 根据工具名称创建对应的处理函数
            if tool_name == "get_model_params":
                @self.mcp.tool(
                    name=schema.name,
                    description=schema.description,
                    output_schema=schema.inputSchema
                )
                async def get_model_params_handler(model_name: str, basin_id: str):
                    """获取模型参数"""
                    try:
                        result = self.tools.get_model_params(model_name=model_name, basin_id=basin_id)
                        content = json.dumps(result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                    except Exception as e:
                        logger.error(f"工具调用失败: {e}")
                        error_result = {"success": False, "error": f"工具调用失败: {str(e)}"}
                        content = json.dumps(error_result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                        
            elif tool_name == "prepare_data":
                @self.mcp.tool(
                    name=schema.name,
                    description=schema.description,
                    output_schema=schema.inputSchema
                )
                async def prepare_data_handler(basin_id: str, start_date: str, end_date: str):
                    """准备数据"""
                    try:
                        result = self.tools.prepare_data(basin_id=basin_id, start_date=start_date, end_date=end_date)
                        content = json.dumps(result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                    except Exception as e:
                        logger.error(f"工具调用失败: {e}")
                        error_result = {"success": False, "error": f"工具调用失败: {str(e)}"}
                        content = json.dumps(error_result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                        
            elif tool_name == "calibrate_model":
                @self.mcp.tool(
                    name=schema.name,
                    description=schema.description,
                    output_schema=schema.inputSchema
                )
                async def calibrate_model_handler(model_name: str, basin_id: str, start_date: str, end_date: str):
                    """校准模型"""
                    try:
                        result = self.tools.calibrate_model(
                            model_name=model_name,
                            basin_id=basin_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        content = json.dumps(result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                    except Exception as e:
                        logger.error(f"工具调用失败: {e}")
                        error_result = {"success": False, "error": f"工具调用失败: {str(e)}"}
                        content = json.dumps(error_result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                        
            elif tool_name == "evaluate_model":
                @self.mcp.tool(
                    name=schema.name,
                    description=schema.description,
                    output_schema=schema.inputSchema
                )
                async def evaluate_model_handler(model_name: str, basin_id: str, start_date: str, end_date: str):
                    """评估模型"""
                    try:
                        result = self.tools.evaluate_model(
                            model_name=model_name,
                            basin_id=basin_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                        content = json.dumps(result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
                    except Exception as e:
                        logger.error(f"工具调用失败: {e}")
                        error_result = {"success": False, "error": f"工具调用失败: {str(e)}"}
                        content = json.dumps(error_result, indent=2, ensure_ascii=False)
                        return TextContent(type="text", text=content)
    
    async def start(self, transport_type: str = "stdio"):
        """启动MCP服务器"""
        if not MCP_AVAILABLE:
            logger.error("无法启动MCP服务器：FastMCP库未安装")
            return
            
        # 确保服务器实例正确初始化
        if not self.mcp:
            self.mcp = FastMCP(self.name)
            self._setup_tools()
            
        try:
            logger.info(f"启动水文模型MCP服务器: {self.name} v{self.version}")
            
            if transport_type == "stdio":
                await self.mcp.run_async()
            else:
                logger.error(f"不支持的传输类型: {transport_type}")
                
        except Exception as e:
            logger.error(f"MCP服务器启动失败: {e}")
            import traceback
            logger.error(f"错误详情:\n{traceback.format_exc()}")
            raise
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表（兼容模式）"""
        tools = []
        for tool_name, schema in TOOL_SCHEMAS.items():
            tools.append({
                "name": schema.name,
                "description": schema.description,
                "inputSchema": schema.inputSchema
            })
        return tools
    
    async def call_tool_direct(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """直接调用工具（兼容模式）"""
        try:
            logger.info(f"直接调用工具: {name}, 参数: {arguments}")
            
            if name == "get_model_params":
                return self.tools.get_model_params(**arguments)
            elif name == "prepare_data":
                return self.tools.prepare_data(**arguments) 
            elif name == "calibrate_model":
                return self.tools.calibrate_model(**arguments)
            elif name == "evaluate_model":
                return self.tools.evaluate_model(**arguments)
            else:
                return {
                    "success": False,
                    "error": f"未知工具: {name}"
                }
                
        except Exception as e:
            logger.error(f"工具调用失败: {e}")
            return {
                "success": False,
                "error": f"工具调用失败: {str(e)}"
            }


# 创建全局服务器实例
hydro_mcp_server = HydroMCPServer()


async def main():
    """主函数，启动MCP服务器"""
    import sys
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 确保服务器实例正确初始化
        if not hydro_mcp_server.mcp and MCP_AVAILABLE:
            hydro_mcp_server.mcp = FastMCP(hydro_mcp_server.name)
            hydro_mcp_server._setup_tools()
        
        # 启动服务器
        logger.info(f"启动MCP服务器: {hydro_mcp_server.name} v{hydro_mcp_server.version}")
        await hydro_mcp_server.start()
            
    except KeyboardInterrupt:
        logger.info("收到中断信号，停止服务器")
    except Exception as e:
        logger.error(f"服务器运行出错: {e}")
        import traceback
        logger.error(f"错误详情:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    # 启动MCP服务器
    asyncio.run(main())
