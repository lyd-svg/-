"""
智能体运行
run_agent / run_agent_with_retry / run_agent_streamed

重要：MCP session 生命周期由 Runner 内部的 MCPManager 管理。
我们只做 HTTP 存活检查，不做 MCP 协议级别的 session 操作。
Runner.run() 完成后，MCPManager.cleanup 关闭 session 但不置 None，
因此在每次 run 之后清空 session 引用，防止下次 runner 复用已关闭的 session。
"""
import asyncio
from agents import Runner
from agents.run import RunResult

from .config import _MCP_SERVERS, _last_checked
from .mcp_connection import ensure_all_mcp_connected, _reset_server_locks
from .agents import main_agent
from .history import _sanitize_messages, _trim_history, MAX_HISTORY


def _clear_sessions():
    """清空所有 MCP session（Runner 的 cleanup 不置 None，需手动清空）"""
    for s in _MCP_SERVERS:
        s.session = None



async def run_agent(user_input: str, previous_result: RunResult | None = None,
                    max_history: int = MAX_HISTORY) -> RunResult:
    """运行主智能体，支持多轮对话上下文传递"""
    await ensure_all_mcp_connected()

    if previous_result is not None and max_history > 0:
        input_messages = _sanitize_messages(
            _trim_history(previous_result.to_input_list(), max_history)
        )
        input_messages.append({"role": "user", "content": user_input})
        input_data = input_messages
    else:
        input_data = user_input

    # 让 Runner 内部的 MCPManager 接管 session（已有 session 则复用）
    result = await Runner.run(
        main_agent,
        input=input_data,
        max_turns=50,
    )

    # Runner 完成后，MCPManager.cleanup 关闭了 session 但不置 None
    # 清空引用，下次 run 时 MCPManager 会重建
    _clear_sessions()
    return result


async def run_agent_with_retry(user_input: str, previous_result: RunResult | None = None,
                                max_history: int = MAX_HISTORY) -> RunResult:
    """运行智能体，连接断开时自动重连重试"""
    try:
        return await run_agent(user_input, previous_result, max_history)
    except ConnectionError:
        print("[MCP] 连接异常，正在重连后重试...")
        for s in _MCP_SERVERS:
            s.session = None
        _last_checked.clear()
        return await run_agent(user_input, previous_result, max_history)


async def run_agent_streamed(user_input: str, previous_result: RunResult | None = None,
                             max_history: int = MAX_HISTORY):
    """流式运行智能体，逐条 yield StreamEvent"""
    for attempt in range(2):
        await ensure_all_mcp_connected()

        if previous_result is not None and max_history > 0:
            input_messages = _sanitize_messages(
                _trim_history(previous_result.to_input_list(), max_history)
            )
            input_messages.append({"role": "user", "content": user_input})
            input_data = input_messages
        else:
            input_data = user_input

        try:
            streaming = Runner.run_streamed(
                main_agent,
                input=input_data,
                max_turns=50,
            )
            async for event in streaming.stream_events():
                yield event
            break
        except Exception as e:
            msg = str(e)
            if "tool_calls" in msg and "400" in msg:
                print(f"[Agent] 检测到 tool_calls 消息不配对，清空历史重试: {msg[:100]}")
                previous_result = None
                continue
            raise
        finally:
            _clear_sessions()
