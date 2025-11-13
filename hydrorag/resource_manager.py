"""
Author: Claude Code
Date: 2025-10-12 16:30:00
LastEditTime: 2025-10-12 16:30:00
LastEditors: Claude Code
Description: 资源管理模块，确保httpx连接等资源被正确清理，避免端口占用问题
FilePath: \HydroAgent\hydrorag\resource_manager.py
Copyright (c) 2023-2024 HydroAgent. All rights reserved.
"""

import gc
import logging
import asyncio
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

logger = logging.getLogger(__name__)


class ResourceManager:
    """资源管理器 - 负责清理嵌入模型的httpx连接等资源"""

    @staticmethod
    def cleanup_embedding_client(embeddings: Any, timeout: float = 5.0) -> bool:
        """
        清理嵌入模型的客户端连接

        Args:
            embeddings: 嵌入模型实例
            timeout: 清理超时时间（秒）

        Returns:
            bool: 清理是否成功
        """
        try:
            if not embeddings:
                return True

            # 尝试关闭同步客户端
            if hasattr(embeddings, 'client'):
                if hasattr(embeddings.client, 'close'):
                    try:
                        embeddings.client.close()
                        logger.debug("成功关闭同步客户端")
                    except Exception as e:
                        logger.warning(f"关闭同步客户端失败: {e}")

                # 尝试关闭异步客户端（httpx）
                if hasattr(embeddings.client, 'aclose'):
                    try:
                        # 获取或创建事件循环
                        loop = ResourceManager._get_event_loop()
                        if loop:
                            # 在线程池中执行异步清理，带超时保护
                            with ThreadPoolExecutor(max_workers=1) as executor:
                                future = executor.submit(
                                    loop.run_until_complete,
                                    embeddings.client.aclose()
                                )
                                try:
                                    future.result(timeout=timeout)
                                    logger.debug("成功关闭异步客户端")
                                except FutureTimeoutError:
                                    logger.warning(f"关闭异步客户端超时（{timeout}秒）")
                                except Exception as e:
                                    logger.warning(f"关闭异步客户端失败: {e}")
                    except Exception as e:
                        logger.warning(f"异步客户端清理异常: {e}")

            # 删除对象引用
            try:
                del embeddings
            except:
                pass

            # 强制垃圾回收
            gc.collect()

            logger.debug("嵌入模型客户端资源清理完成")
            return True

        except Exception as e:
            logger.error(f"清理嵌入模型客户端失败: {e}")
            return False

    @staticmethod
    def _get_event_loop() -> Optional[asyncio.AbstractEventLoop]:
        """获取或创建事件循环"""
        try:
            # 尝试获取当前循环
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop
        except RuntimeError:
            # 如果没有循环，创建新的
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop
            except Exception as e:
                logger.warning(f"无法创建事件循环: {e}")
                return None

    @staticmethod
    def safe_cleanup(obj: Any, cleanup_method: str = 'close') -> bool:
        """
        安全清理任意对象的资源

        Args:
            obj: 需要清理的对象
            cleanup_method: 清理方法名（默认为'close'）

        Returns:
            bool: 清理是否成功
        """
        try:
            if not obj:
                return True

            if hasattr(obj, cleanup_method):
                cleanup_fn = getattr(obj, cleanup_method)
                if callable(cleanup_fn):
                    cleanup_fn()
                    logger.debug(f"成功调用 {cleanup_method} 方法")
                    return True

            return True

        except Exception as e:
            logger.warning(f"安全清理失败: {e}")
            return False

    @staticmethod
    def force_gc(generation: int = 2) -> dict:
        """
        强制垃圾回收

        Args:
            generation: GC代数（0-2）

        Returns:
            dict: 回收统计信息
        """
        try:
            before = gc.get_count()
            collected = gc.collect(generation)
            after = gc.get_count()

            stats = {
                'collected': collected,
                'before': before,
                'after': after,
                'generation': generation
            }

            logger.debug(f"强制GC完成: {stats}")
            return stats

        except Exception as e:
            logger.error(f"强制GC失败: {e}")
            return {'error': str(e)}


class CleanupContext:
    """清理上下文管理器 - 确保资源在使用后被清理"""

    def __init__(self, resource: Any, cleanup_func=None):
        """
        初始化清理上下文

        Args:
            resource: 需要管理的资源
            cleanup_func: 自定义清理函数
        """
        self.resource = resource
        self.cleanup_func = cleanup_func or ResourceManager.cleanup_embedding_client

    def __enter__(self):
        """进入上下文"""
        return self.resource

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，执行清理"""
        try:
            if self.cleanup_func:
                self.cleanup_func(self.resource)
        except Exception as e:
            logger.error(f"上下文清理失败: {e}")

        # 不抑制异常
        return False


class EmbeddingClientPool:
    """嵌入模型客户端池 - 复用客户端，减少创建/销毁开销"""

    def __init__(self, max_size: int = 5):
        """
        初始化客户端池

        Args:
            max_size: 最大客户端数量
        """
        self.max_size = max_size
        self.pool = []
        self.active = []

    def acquire(self, create_func) -> Any:
        """
        获取客户端

        Args:
            create_func: 创建客户端的函数

        Returns:
            客户端实例
        """
        try:
            # 从池中获取
            if self.pool:
                client = self.pool.pop()
                self.active.append(client)
                logger.debug("从池中获取客户端")
                return client

            # 创建新客户端
            client = create_func()
            self.active.append(client)
            logger.debug("创建新客户端")
            return client

        except Exception as e:
            logger.error(f"获取客户端失败: {e}")
            raise

    def release(self, client: Any) -> bool:
        """
        释放客户端回池

        Args:
            client: 客户端实例

        Returns:
            bool: 释放是否成功
        """
        try:
            if client in self.active:
                self.active.remove(client)

                # 如果池未满，放回池中
                if len(self.pool) < self.max_size:
                    self.pool.append(client)
                    logger.debug("客户端放回池中")
                else:
                    # 池已满，清理客户端
                    ResourceManager.cleanup_embedding_client(client)
                    logger.debug("池已满，清理客户端")

                return True

            return False

        except Exception as e:
            logger.error(f"释放客户端失败: {e}")
            return False

    def cleanup_all(self) -> int:
        """
        清理所有客户端

        Returns:
            int: 清理的客户端数量
        """
        cleaned = 0

        try:
            # 清理活动客户端
            for client in self.active:
                if ResourceManager.cleanup_embedding_client(client):
                    cleaned += 1

            # 清理池中客户端
            for client in self.pool:
                if ResourceManager.cleanup_embedding_client(client):
                    cleaned += 1

            self.active.clear()
            self.pool.clear()

            logger.info(f"清理了 {cleaned} 个客户端")
            return cleaned

        except Exception as e:
            logger.error(f"清理所有客户端失败: {e}")
            return cleaned
