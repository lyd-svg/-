"""
Streamlit 共享工具模块
提供 MCP 客户端调用、异步执行器等跨页面共享的功能
"""
import asyncio
import atexit
import concurrent.futures
import os
from pathlib import Path
from typing import Any

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent

# ── 执行器 ──
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2)
_TIMEOUT = 60


@atexit.register
def _cleanup_pool():
    """应用退出时优雅关闭线程池，避免事件循环冲突"""
    _POOL.shutdown(wait=False)


def run_async(coro, timeout: int = _TIMEOUT) -> Any:
    """在独立线程中运行协程并等待结果"""
    future = _POOL.submit(lambda: asyncio.run(coro))
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        raise TimeoutError(f"操作超时（超过 {timeout} 秒）")


# ── MCP 工具调用（通过 SSE 直连） ──

async def _call_tool(server_url: str, tool_name: str, arguments: dict | None = None):
    """连接到 MCP Streamable HTTP 服务器并调用工具"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url=f"{server_url}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments or {})
            return result


async def _list_tools(server_url: str):
    """列出 MCP 服务器的所有工具"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    async with streamable_http_client(url=f"{server_url}/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result


def call_mcp_tool(server_url: str, tool_name: str, arguments: dict | None = None) -> Any:
    """同步调用 MCP 工具"""
    return run_async(_call_tool(server_url, tool_name, arguments), timeout=120)


def list_mcp_tools(server_url: str) -> list:
    """同步列出 MCP 工具"""
    return run_async(_list_tools(server_url), timeout=30)


# ── 文件路径辅助 ──

def get_knowledge_raw_dir() -> Path:
    """知识库原始文件目录"""
    return ROOT_DIR / "knowledge_base" / "raw"


def get_db_dir() -> Path:
    """上传的数据库文件目录"""
    db_dir = ROOT_DIR / "databases"
    db_dir.mkdir(exist_ok=True)
    return db_dir


# ── MCP 服务器地址 ──

RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:8002")
DB_SERVER_URL = os.getenv("DB_SERVER_URL", "http://localhost:8000")
