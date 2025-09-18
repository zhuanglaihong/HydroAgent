"""
filepath.py - 文件路径处理工具包

功能：
1. 规范化路径格式（统一分隔符）
2. 检查路径是否存在
3. 验证路径格式是否合法
4. 将相对路径转换为绝对路径
5. 修复常见路径问题
6. 智能处理AI生成的路径问题
"""

import os
import re
import sys
from pathlib import Path
from typing import Union, Tuple, Optional

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