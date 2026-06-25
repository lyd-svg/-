"""
异步任务执行器
Streamlit 主线程有 WebSocket 事件循环，故在独立后台线程中跑 asyncio

注意：不主动清理 MCP SSE 会话。线程退出时 asyncio.run() 销毁事件循环，
所有异步生成器会自动 GC，连接自然关闭。强制 close() 反而会触发
anyio cancel scope 跨任务报错。
"""
import asyncio
import concurrent.futures

from agents.tracing import set_trace_processors, set_tracing_disabled

from agent_system import run_agent_with_retry
from .progress import _ProgressBuffer, _StreamlitTracingProcessor

_AGENT_TIMEOUT = 300  # 5 分钟，覆盖复杂多步查询（12 DB + 3 VIZ 约需 3-4 分钟）
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)


def run_async(coro):
    """在独立线程中运行协程并等待结果"""
    future = _POOL.submit(lambda: asyncio.run(coro))
    try:
        return future.result(timeout=_AGENT_TIMEOUT)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"操作超时（超过 {_AGENT_TIMEOUT} 秒）")


def run_agent_with_progress(user_input, previous_result, max_history):
    """运行智能体，返回 (Future, ProgressBuffer) 用于流式进度显示"""
    buf = _ProgressBuffer()

    set_tracing_disabled(False)
    set_trace_processors([_StreamlitTracingProcessor(buf)])

    future = _POOL.submit(
        lambda: asyncio.run(
            run_agent_with_retry(user_input, previous_result, max_history)
        )
    )
    return future, buf
