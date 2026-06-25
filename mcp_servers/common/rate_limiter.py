"""
三层限流器：并发控制 + 频率限制 + 队列溢出

消除 mcp_db_server / mcp_analysis_server / mcp_rag_server 中的重复实现。

用法：
    from mcp_servers.common import RateLimiter, with_rate_limit

    _rate_limiter = RateLimiter(max_concurrent=5, max_per_second=20, max_queue=30)

    @with_rate_limit(_rate_limiter)
    async def my_tool(...):
        ...
"""
import asyncio
import threading
import time
import functools
import contextlib


class RateLimiter:
    """三层限流：并发控制 + 频率限制 + 队列溢出"""

    def __init__(self, max_concurrent: int = 10, max_per_second: int = 50,
                 max_queue: int = 50):
        self._max_concurrent = max_concurrent
        self._max_rps = max_per_second
        self._max_queue = max_queue
        self._waiting = 0
        self._timestamps: list[float] = []
        self._sem = None
        self._mtx_lock = None
        self._init_lock = threading.Lock()
        self._loop = None

    def _ensure(self):
        """
        惰性初始化 asyncio 原语，确保在运行中的事件循环中创建。
        当 MCP 服务器重启/重载导致事件循环变化时自动重建。
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # 没有运行中的事件循环时跳过

        if self._sem is not None and self._loop is current_loop:
            return  # 已在当前事件循环中初始化过

        with self._init_lock:
            if self._sem is not None and self._loop is current_loop:
                return
            self._sem = asyncio.Semaphore(self._max_concurrent)
            self._mtx_lock = asyncio.Lock()
            self._loop = current_loop

    async def acquire(self):
        """获取执行许可，失败则抛出 RuntimeError"""
        self._ensure()
        async with self._mtx_lock:
            now = time.time()
            self._timestamps = [t for t in self._timestamps if now - t < 1.0]
            if len(self._timestamps) >= self._max_rps:
                raise RuntimeError(
                    f"请求太频繁（限 {self._max_rps} 次/秒），请稍后重试")
            self._timestamps.append(now)
            if self._waiting >= self._max_queue:
                raise RuntimeError(
                    f"系统繁忙（排队 {self._max_queue}+），请稍后重试")
            self._waiting += 1
        try:
            await self._sem.acquire()
        finally:
            async with self._mtx_lock:
                self._waiting -= 1

    def release(self):
        self._sem.release()

    @contextlib.asynccontextmanager
    async def limit(self):
        """限流上下文管理器，使用此实例的限制参数"""
        await self.acquire()
        try:
            yield
        finally:
            self.release()


def with_rate_limit(limiter: RateLimiter):
    """装饰器：为 MCP 工具函数加上三层限流保护

    用法：
        _rate_limiter = RateLimiter(max_concurrent=5, max_per_second=20, max_queue=30)

        @with_rate_limit(_rate_limiter)
        async def my_mcp_tool(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                async with limiter.limit():
                    return await func(*args, **kwargs)
            except RuntimeError as e:
                return f"## 请求受限\n\n{str(e)}"
        return wrapper
    return decorator
