"""
Author: zhuanglaihong
Date: 2024-09-26 16:45:00
LastEditTime: 2024-09-26 16:45:00
LastEditors: zhuanglaihong
Description: 文件路径处理工具函数 - 统一处理项目中的文件路径问题
FilePath: \\HydroAgent\\utils\\filepath.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.

filepath.py - 文件路径处理工具包

功能：
1. 规范化路径格式（统一分隔符）
2. 检查路径是否存在
3. 验证路径格式是否合法
4. 将相对路径转换为绝对路径
5. 修复常见路径问题
6. 智能处理AI生成的路径问题
7. 项目特定的路径处理（数据目录、结果目录等）
"""

import os
import re
import sys
from pathlib import Path
from typing import Union, Tuple, Optional, Dict, Any

# 导入项目配置
try:
    import definitions
except ImportError:
    # 如果无法导入definitions，使用默认值
    class definitions:
        PROJECT_DIR = os.getcwd()
        RESULT_DIR = "result"
        DATASET_DIR = "data/camels_11532500"

# 定义操作系统类型常量
WINDOWS = sys.platform.startswith('win')
LINUX = sys.platform.startswith('linux')
MACOS = sys.platform.startswith('darwin')

def normalize_path(path: Union[str, Path]) -> str:
    """
    规范化文件路径，统一使用当前操作系统的正确分隔符
    
    参数:
        path: 原始路径字符串或Path对象
        
    返回:
        规范化后的路径字符串
        
    示例:
        >>> normalize_path("C:\\Users\\test//doc.txt")
        'C:\\Users\\test\\doc.txt'  # Windows
        '/home/user/test/doc.txt'   # Linux/Mac
    """
    # 如果输入是Path对象，直接转换为字符串
    if isinstance(path, Path):
        return str(path)
    
    # 处理AI生成的路径常见问题
    # 1. 替换多余的分隔符
    # 2. 替换错误的分隔符
    # 3. 处理混合分隔符
    if WINDOWS:
        # Windows系统处理
        path = re.sub(r'[/\\]+', os.sep, path)
        # 处理AI可能生成的类Unix路径
        if path.startswith('/'):
            # 尝试将类Unix路径转换为Windows路径
            if len(path) > 2 and path[1] == '/':
                # 处理类似 //C:/Users 的路径
                path = path[1:]
            else:
                # 处理类似 /mnt/c/Users 的路径 (WSL风格)
                if path.startswith('/mnt/'):
                    drive = path[5].upper() + ':'
                    path = drive + path[6:]
    else:
        # Linux/Mac系统处理
        path = re.sub(r'[/\\]+', os.sep, path)
        # 处理AI可能生成的Windows路径
        if ':' in path and len(path) > 1 and path[1] == ':':
            # 处理类似 C:\Users 的路径
            drive, rest = path.split(':', 1)
            path = os.path.join('/mnt', drive.lower(), rest.replace('\\', '/'))
    
    # 使用pathlib进行最终规范化
    return str(Path(path).resolve())

def path_exists(path: Union[str, Path]) -> bool:
    """
    检查路径是否存在（文件或目录）
    
    参数:
        path: 要检查的路径
        
    返回:
        bool: 路径是否存在
    """
    normalized = normalize_path(path)
    return os.path.exists(normalized)

def is_valid_path(path: Union[str, Path]) -> Tuple[bool, Optional[str]]:
    """
    检查路径格式是否合法（不检查路径是否存在）
    
    参数:
        path: 要检查的路径
        
    返回:
        tuple: (是否合法, 错误信息)
    """
    normalized = normalize_path(path)
    
    # 检查空路径
    if not path:
        return False, "路径不能为空"
    
    # Windows特定检查
    if WINDOWS:
        # 检查非法字符
        illegal_chars = r'<>:"|?*'
        if any(char in normalized for char in illegal_chars):
            return False, f"路径包含非法字符: {illegal_chars}"
        
        # 检查保留文件名
        reserved_names = [
            'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
            'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
            'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
        ]
        filename = os.path.basename(normalized)
        if filename.upper() in reserved_names:
            return False, f"文件名是保留名称: {filename}"
    
    # Linux/Mac特定检查
    else:
        # 检查非法字符 (Linux/Mac只禁止空字符和/)
        if '\x00' in normalized:
            return False, "路径包含空字符"
        
        # 检查路径是否以/开头（绝对路径要求）
        if not normalized.startswith('/') and ':' in normalized:
            return False, "类Unix系统路径应以/开头"
    
    # 通用检查
    try:
        # 尝试创建Path对象验证路径
        Path(normalized)
        return True, None
    except Exception as e:
        return False, f"无效路径格式: {str(e)}"

def to_absolute_path(path: Union[str, Path], base_dir: Union[str, Path, None] = None) -> str:
    """
    将相对路径转换为绝对路径
    
    参数:
        path: 要转换的路径
        base_dir: 相对路径的基准目录（默认为当前工作目录）
        
    返回:
        绝对路径字符串
    """
    normalized = normalize_path(path)
    
    # 如果已经是绝对路径，直接返回
    if os.path.isabs(normalized):
        return normalized
    
    # 确定基准目录
    if base_dir is None:
        base = os.getcwd()
    else:
        base = normalize_path(base_dir)
        if not os.path.isabs(base):
            base = os.path.abspath(base)
    
    # 组合路径
    return os.path.join(base, normalized)

def correct_path(path: Union[str, Path], base_dir: Union[str, Path, None] = None) -> str:
    """
    修复路径的常见问题：
    1. 规范化分隔符
    2. 转换为绝对路径
    3. 修复AI生成的路径问题
    
    参数:
        path: 要修复的路径
        base_dir: 相对路径的基准目录（默认为当前工作目录）
        
    返回:
        修复后的路径字符串
    """
    # 规范化路径
    normalized = normalize_path(path)
    
    # 转换为绝对路径
    absolute = to_absolute_path(normalized, base_dir)
    
    # 处理AI生成的特定问题
    if WINDOWS:
        # 修复AI可能生成的双斜杠问题（除了网络路径）
        if not absolute.startswith('\\\\'):
            absolute = absolute.replace('\\\\', '\\')
    else:
        # 修复AI可能生成的Windows风格路径
        if ':\\' in absolute:
            parts = absolute.split(':\\')
            if len(parts) > 1:
                drive = parts[0].lower()
                rest = '\\'.join(parts[1:])
                absolute = f"/mnt/{drive}/{rest}"
    
    # 使用pathlib进行最终清理
    return str(Path(absolute).resolve())

def safe_join(base: Union[str, Path], *paths: Union[str, Path]) -> str:
    """
    安全地组合路径，防止路径遍历攻击
    
    参数:
        base: 基础路径
        *paths: 要组合的路径部分
        
    返回:
        组合后的安全路径
    """
    base_path = Path(correct_path(base))
    full_path = base_path
    
    for path in paths:
        # 规范化每个部分
        part = str(path).replace('\\', '/').strip('/')
        # 防止路径遍历
        if part.startswith('../') or part == '..':
            raise ValueError("检测到路径遍历尝试")
        full_path = full_path / part
    
    return str(full_path.resolve())

def is_subpath(child: Union[str, Path], parent: Union[str, Path]) -> bool:
    """
    检查一个路径是否是另一个路径的子路径
    
    参数:
        child: 要检查的子路径
        parent: 父路径
        
    返回:
        bool: child是否是parent的子路径
    """
    parent_path = Path(correct_path(parent)).resolve()
    child_path = Path(correct_path(child)).resolve()
    
    try:
        # 检查child_path是否在parent_path下
        return parent_path in child_path.parents or parent_path == child_path
    except ValueError:
        # 不同驱动器的情况
        return False

def get_relative_path(target: Union[str, Path], base: Union[str, Path]) -> str:
    """
    获取相对于基础路径的相对路径
    
    参数:
        target: 目标路径
        base: 基础路径
        
    返回:
        相对路径字符串
    """
    base_path = Path(correct_path(base)).resolve()
    target_path = Path(correct_path(target)).resolve()
    
    try:
        return os.path.relpath(str(target_path), str(base_path))
    except ValueError:
        # 不同驱动器的情况
        return str(target_path)

# 测试函数
if __name__ == "__main__":
    # 测试路径
    test_paths = [
        "C:\\Users\\test//doc.txt",  # Windows多余分隔符
        "/home/user//doc.txt",       # Linux多余分隔符
        "C:/Users/test/doc.txt",     # Windows混合分隔符
        "\\Users\\test\\doc.txt",    # Windows相对路径错误
        "doc.txt",                   # 相对路径
        "invalid|file.txt",          # 非法字符
        "CON",                       # Windows保留名称
        "/mnt/c/Users/test",         # WSL路径
    ]
    
    print("路径规范化测试:")
    for path in test_paths:
        print(f"原始: {path} -> 规范化: {normalize_path(path)}")
    
    print("\n路径存在测试:")
    for path in test_paths:
        exists = path_exists(path)
        print(f"{path} 存在: {exists}")
    
    print("\n路径有效性测试:")
    for path in test_paths:
        valid, reason = is_valid_path(path)
        print(f"{path} 有效: {valid}, 原因: {reason if not valid else '有效'}")
    
    print("\n转换为绝对路径测试:")
    for path in test_paths:
        abs_path = to_absolute_path(path)
        print(f"{path} -> 绝对路径: {abs_path}")
    
    print("\n路径修复测试:")
    for path in test_paths:
        fixed = correct_path(path)
        print(f"{path} -> 修复后: {fixed}")
    
    print("\n安全路径组合测试:")
    try:
        result = safe_join("/base/path", "subdir", "../../secret.txt")
        print(f"安全组合结果: {result}")
    except ValueError as e:
        print(f"安全组合捕获: {str(e)}")
    
    print("\n子路径检查测试:")
    parent = "/base/path"
    child = "/base/path/subdir/file.txt"
    print(f"{child} 是 {parent} 的子路径: {is_subpath(child, parent)}")
    
    print("\n相对路径获取测试:")
    base = "/base/path"
    target = "/base/path/subdir/file.txt"
    print(f"{target} 相对于 {base}: {get_relative_path(target, base)}")


# ============================================================================
# 项目特定的路径处理函数
# ============================================================================

def get_project_root() -> Path:
    """
    获取项目根目录路径

    Returns:
        Path: 项目根目录路径
    """
    return Path(definitions.PROJECT_DIR)


def resolve_data_path(data_dir: Union[str, Path]) -> Path:
    """
    解析数据目录路径

    Args:
        data_dir: 数据目录路径（可以是相对或绝对路径）

    Returns:
        Path: 解析后的绝对路径
    """
    data_path = Path(data_dir)

    if data_path.is_absolute():
        return data_path

    # 如果是相对路径，先尝试相对于项目根目录
    project_relative = get_project_root() / data_path
    if project_relative.exists():
        return project_relative

    # 然后尝试相对于DATASET_DIR
    dataset_relative = Path(definitions.DATASET_DIR) / data_path
    if dataset_relative.exists():
        return dataset_relative.resolve()

    # 最后返回相对于项目根目录的路径（即使不存在）
    return project_relative


def resolve_result_path(result_dir: Union[str, Path]) -> Path:
    """
    解析结果目录路径

    Args:
        result_dir: 结果目录路径（可以是相对或绝对路径）

    Returns:
        Path: 解析后的绝对路径
    """
    result_path = Path(result_dir)

    if result_path.is_absolute():
        return result_path

    # 如果是相对路径，先尝试相对于项目根目录
    project_relative = get_project_root() / result_path
    if project_relative.exists():
        return project_relative

    # 然后尝试相对于RESULT_DIR
    result_relative = Path(definitions.RESULT_DIR) / result_path
    return to_absolute_path(result_relative)


def process_workflow_paths(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理工作流中的路径参数，将相对路径转换为绝对路径

    Args:
        workflow: 工作流字典

    Returns:
        Dict[str, Any]: 处理后的工作流字典
    """
    processed_workflow = workflow.copy()

    if "tasks" in processed_workflow:
        for task in processed_workflow["tasks"]:
            if "parameters" in task:
                parameters = task["parameters"]

                # 处理常见的路径参数
                if "data_dir" in parameters:
                    parameters["data_dir"] = str(resolve_data_path(parameters["data_dir"]))

                if "result_dir" in parameters:
                    parameters["result_dir"] = str(resolve_result_path(parameters["result_dir"]))

                if "output_dir" in parameters:
                    parameters["output_dir"] = str(to_absolute_path(parameters["output_dir"]))

                if "input_file" in parameters:
                    parameters["input_file"] = str(to_absolute_path(parameters["input_file"]))

                if "output_file" in parameters:
                    parameters["output_file"] = str(to_absolute_path(parameters["output_file"]))

                if "config_file" in parameters:
                    parameters["config_file"] = str(to_absolute_path(parameters["config_file"]))

                # 处理其他可能包含路径的参数
                for key, value in parameters.items():
                    if isinstance(value, str) and value:  # 确保不是空字符串
                        # 检查是否是路径格式的字符串（包含路径分隔符且不是参数引用）
                        if (("/" in value or "\\" in value) and not value.startswith("${") and len(value) > 1):
                            # 尝试解析为路径
                            try:
                                # 使用简单的绝对路径转换
                                if not os.path.isabs(value):
                                    resolved_path = os.path.abspath(value)
                                else:
                                    resolved_path = value
                                parameters[key] = resolved_path
                            except Exception as e:
                                # 如果解析失败，保持原值
                                pass

    return processed_workflow


def ensure_directory_exists(path: Union[str, Path]) -> Path:
    """
    确保目录存在，如果不存在则创建

    Args:
        path: 目录路径

    Returns:
        Path: 确保存在的目录路径
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def create_output_path(base_dir: Union[str, Path], filename: str) -> Path:
    """
    创建输出文件路径，自动确保目录存在

    Args:
        base_dir: 基础目录
        filename: 文件名

    Returns:
        Path: 完整的输出文件路径
    """
    base_path = to_absolute_path(base_dir)
    ensure_directory_exists(base_path)
    return Path(base_path) / filename


def is_path_parameter(value: Any) -> bool:
    """
    判断参数值是否可能是路径

    Args:
        value: 参数值

    Returns:
        bool: 是否是路径参数
    """
    if not isinstance(value, str):
        return False

    # 排除参数引用格式
    if value.startswith("${") and value.endswith("}"):
        return False

    # 检查是否包含路径分隔符
    if "/" in value or "\\" in value:
        return True

    # 检查是否是已知的路径模式
    path_patterns = ["data", "result", "output", "input", "temp", "cache", "log"]
    return any(pattern in value.lower() for pattern in path_patterns)


def convert_paths_to_absolute(parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    将参数字典中的路径值转换为绝对路径

    Args:
        parameters: 参数字典

    Returns:
        Dict[str, Any]: 转换后的参数字典
    """
    converted_params = parameters.copy()

    for key, value in converted_params.items():
        if is_path_parameter(value):
            try:
                # 根据参数名称选择合适的路径解析方式
                if "data" in key.lower():
                    converted_params[key] = str(resolve_data_path(value))
                elif "result" in key.lower() or "output" in key.lower():
                    converted_params[key] = str(resolve_result_path(value))
                else:
                    converted_params[key] = str(to_absolute_path(value))
            except Exception:
                # 解析失败时保持原值
                pass

    return converted_params


def validate_path_exists(path: Union[str, Path], create_if_missing: bool = False) -> bool:
    """
    验证路径是否存在

    Args:
        path: 要验证的路径
        create_if_missing: 如果缺失是否创建（仅对目录有效）

    Returns:
        bool: 路径是否存在或成功创建
    """
    path = Path(path)

    if path.exists():
        return True

    if create_if_missing and not path.suffix:  # 没有扩展名，视为目录
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False

    return False