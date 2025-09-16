"""
水文模型MCP客户端
用于Agent连接和使用MCP服务端的工具
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

# FastMCP客户端相关导入
try:
    from fastmcp import FastMCP
    from fastmcp.client import Client
    from mcp.types import CallToolRequest, TextContent
    MCP_CLIENT_AVAILABLE = True
except ImportError:
    print("FastMCP客户端库未安装，使用兼容模式")
    MCP_CLIENT_AVAILABLE = False

from .server import hydro_mcp_server

logger = logging.getLogger(__name__)


class HydroMCPClient:
    """水文模型MCP客户端"""
    
    def __init__(self, server_command: Optional[List[str]] = None):
        """
        初始化MCP客户端
        
        Args:
            server_command: MCP服务器启动命令，如果为None则使用直接模式
        """
        self.server_command = server_command
        self.client: Optional[Client] = None
        self.available_tools: List[Dict[str, Any]] = []
        
        # 如果没有提供服务器命令，使用直接模式
        self.direct_mode = server_command is None
        
    async def connect(self) -> bool:
        """
        连接到MCP服务器
        
        Returns:
            是否连接成功
        """
        try:
            if self.direct_mode:
                # 直接模式：不通过外部进程，直接使用服务器实例
                logger.info("使用直接模式连接MCP服务器")
                self.available_tools = hydro_mcp_server.get_available_tools()
                return True
                
            elif MCP_CLIENT_AVAILABLE and self.server_command:
                # 外部进程模式：启动外部MCP服务器进程
                logger.info(f"连接到外部MCP服务器: {' '.join(self.server_command)}")
                
                # 创建FastMCP客户端
                self.client = Client(command=self.server_command)
                await self.client.connect()
                
                # 获取可用工具
                tools = await self.client.list_tools()
                self.available_tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.input_schema
                    }
                    for tool in tools
                ]
                
                logger.info(f"获取到 {len(self.available_tools)} 个工具")
                return True
            else:
                logger.error("FastMCP客户端库不可用且未提供服务器命令")
                return False
                
        except Exception as e:
            logger.error(f"连接MCP服务器失败: {e}")
            return False
    
    async def disconnect(self):
        """断开与MCP服务器的连接"""
        try:
            if self.client:
                await self.client.disconnect()
                self.client = None
                logger.info("已断开MCP服务器连接")
        except Exception as e:
            logger.error(f"断开连接失败: {e}")
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """
        获取可用工具列表
        
        Returns:
            工具列表
        """
        return self.available_tools
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        根据名称获取工具信息
        
        Args:
            tool_name: 工具名称
            
        Returns:
            工具信息，如果不存在则返回None
        """
        for tool in self.available_tools:
            if tool["name"] == tool_name:
                return tool
        return None
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用MCP工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            logger.info(f"调用MCP工具: {tool_name}, 参数: {arguments}")
            
            if self.direct_mode:
                # 直接模式：直接调用服务器实例
                result = await hydro_mcp_server.call_tool_direct(tool_name, arguments)
                return result
                
            elif self.client:
                # 外部进程模式：通过FastMCP客户端调用
                response = await self.client.call_tool(tool_name, arguments)
                
                # 解析响应内容
                if response and len(response) > 0:
                    content = response[0]
                    if isinstance(content, TextContent):
                        try:
                            result = json.loads(content.text)
                            return result
                        except json.JSONDecodeError:
                            return {
                                "success": False,
                                "error": f"无法解析工具响应: {content.text}"
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"无效的响应内容类型: {type(content)}"
                        }
                else:
                    return {
                        "success": False,
                        "error": "工具调用无响应内容"
                    }
            else:
                return {
                    "success": False,
                    "error": "未连接到MCP服务器"
                }
                
        except Exception as e:
            logger.error(f"MCP工具调用失败: {e}")
            return {
                "success": False,
                "error": f"工具调用失败: {str(e)}"
            }
    
    async def validate_tool_arguments(self, tool_name: str, arguments: Dict[str, Any]) -> tuple[bool, str]:
        """
        验证工具参数
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            (是否有效, 错误信息)
        """
        tool = self.get_tool_by_name(tool_name)
        if not tool:
            return False, f"工具 {tool_name} 不存在"
        
        schema = tool.get("inputSchema", {})
        required_props = schema.get("required", [])
        properties = schema.get("properties", {})
        
        # 检查必需参数
        for prop in required_props:
            if prop not in arguments:
                return False, f"缺少必需参数: {prop}"
        
        # 检查参数类型（简单验证）
        for prop, value in arguments.items():
            if prop in properties:
                prop_schema = properties[prop]
                expected_type = prop_schema.get("type")
                
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"参数 {prop} 应为字符串类型"
                elif expected_type == "integer" and not isinstance(value, int):
                    return False, f"参数 {prop} 应为整数类型"
                elif expected_type == "array" and not isinstance(value, list):
                    return False, f"参数 {prop} 应为数组类型"
        
        return True, ""


class MCPToolExecutor:
    """MCP工具执行器，用于工作流执行器"""
    
    def __init__(self, server_command: Optional[List[str]] = None):
        """
        初始化MCP工具执行器
        
        Args:
            server_command: MCP服务器启动命令
        """
        self.client = HydroMCPClient(server_command)
        self.connected = False
    
    async def setup(self) -> bool:
        """
        设置执行器，连接到MCP服务器
        
        Returns:
            是否设置成功
        """
        self.connected = await self.client.connect()
        if self.connected:
            tools = self.client.get_available_tools()
            logger.info(f"MCP工具执行器设置成功，可用工具: {[t['name'] for t in tools]}")
        return self.connected
    
    async def cleanup(self):
        """清理资源"""
        await self.client.disconnect()
        self.connected = False
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行MCP工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            执行结果
        """
        if not self.connected:
            return {
                "success": False,
                "error": "MCP客户端未连接"
            }
        
        # 验证参数
        valid, error_msg = await self.client.validate_tool_arguments(tool_name, parameters)
        if not valid:
            return {
                "success": False,
                "error": f"参数验证失败: {error_msg}"
            }
        
        # 执行工具
        return await self.client.call_tool(tool_name, parameters)
    
    def get_available_tools(self) -> List[str]:
        """获取可用工具名称列表"""
        if not self.connected:
            return []
        return [tool["name"] for tool in self.client.get_available_tools()]
    
    def is_tool_available(self, tool_name: str) -> bool:
        """检查工具是否可用"""
        return tool_name in self.get_available_tools()


# 便利函数
async def create_mcp_executor(server_command: Optional[List[str]] = None) -> MCPToolExecutor:
    """
    创建并设置MCP工具执行器
    
    Args:
        server_command: MCP服务器启动命令
        
    Returns:
        已设置的MCP工具执行器
    """
    executor = MCPToolExecutor(server_command)
    success = await executor.setup()
    if not success:
        raise RuntimeError("无法设置MCP工具执行器")
    return executor


# 示例使用
async def main():
    """示例：如何使用MCP客户端"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建客户端（直接模式）
    client = HydroMCPClient()
    
    try:
        # 连接
        if await client.connect():
            print("连接成功！")
            
            # 获取工具列表
            tools = client.get_available_tools()
            print(f"可用工具: {[tool['name'] for tool in tools]}")
            
            # 调用工具示例
            result = await client.call_tool("get_model_params", {"model_name": "gr4j"})
            print(f"工具调用结果: {result}")
            
        else:
            print("连接失败")
            
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
