"""
MCP Server 连接管理
维护 MCP session 供 Runner 使用（Runner 内部 MCPManager 会复用已有 session）

关键问题：
  1. MCPManager.cleanup() 关闭 session 但不置 None
      → 下次 run 误以为 session 可用 → ClosedResourceError
  2. 模块导入时创建的 asyncio.Lock 跨事件循环残锁
      → "Lock bound to a different event loop"

解决：
  - 每次 run 完成后 conversation._clear_sessions() 清空引用
  - 每次连接前 _reset_server_locks() 替换残锁
"""
import time
import asyncio

from agents.mcp import MCPServerStreamableHttp
from .config import _MCP_SERVERS, _last_checked


def _reset_server_locks(server: MCPServerStreamableHttp):
    """
    强制重置 MCP 服务器实例的 asyncio 锁，用当前事件循环的新锁替代。
    """
    for attr in ("_cleanup_lock", "_request_lock"):
        if hasattr(server, attr):
            try:
                setattr(server, attr, asyncio.Lock())
            except RuntimeError:
                pass


async def ensure_mcp_connected(server: MCPServerStreamableHttp,
                                timeout: float = 10) -> bool:
    """确保 MCP Server 有可用 session，无 session 则创建"""
    now = time.monotonic()
    last = _last_checked.get(id(server), 0)
    cache_hit = now - last < 60

    # 已有 session → 快速验证
    if server.session is not None:
        if cache_hit:
            return True
        try:
            async with asyncio.timeout(3):
                await server.session.list_tools()
            _last_checked[id(server)] = now
            return True
        except Exception:
            # session 已失效，清理后重建
            print(f"[MCP] {server.name} session 失效，正在重建...")
            _reset_server_locks(server)
            try:
                await server.cleanup()
            except Exception:
                pass
            server.session = None

    # 无 session 或 session 失效 — 创建新 session
    if not cache_hit:
        _reset_server_locks(server)

    try:
        await asyncio.wait_for(server.connect(), timeout=timeout)
        _last_checked[id(server)] = time.monotonic()
        print(f"[MCP] {server.name} 连接成功")
        return True
    except asyncio.TimeoutError:
        print(f"[MCP] {server.name} 连接超时（{timeout}s），请确认服务已启动")
        return False
    except Exception as e:
        print(f"[MCP] {server.name} 连接失败: {e}")
        return False


async def ensure_all_mcp_connected() -> list[MCPServerStreamableHttp]:
    """确保所有 MCP Server 都有可用 session（无则创建）"""
    # 先全局重置锁，确保新 session 在正确的事件循环中
    for s in _MCP_SERVERS:
        _reset_server_locks(s)

    results = await asyncio.gather(
        *(ensure_mcp_connected(s) for s in _MCP_SERVERS)
    )
    connected = [s for s, ok in zip(_MCP_SERVERS, results) if ok]
    if connected:
        names = ", ".join(s.name for s in connected)
        print(f"[MCP] 已连接 {len(connected)}/{len(_MCP_SERVERS)} 个服务: {names}")
    else:
        print("[MCP] 所有服务均未连接，部分功能不可用")
    print()
    return connected
