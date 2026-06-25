"""
命令行入口
CLI 交互模式 / 单次查询模式
"""
import os
import sys
import time
import asyncio

from dotenv import load_dotenv
load_dotenv()

from agents import Agent, Runner, handoff
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from agents.run import RunResult

from .config import (
    MODEL, DB_SERVER_URL, VIZ_SERVER_URL, RAG_SERVER_URL, CALC_SERVER_URL,
    db_mcp_server, viz_mcp_server, rag_mcp_server, calc_mcp_server,
    _MCP_SERVERS, _last_checked,
)
from .mcp_connection import ensure_all_mcp_connected
from .agents import main_agent, db_agent, viz_agent, rag_agent
from .deepseek_patch import setup_deepseek
from .progress import enable_progress
from .conversation import run_agent_with_retry, run_agent_streamed
from .history import MAX_HISTORY


def _format_friendly_error() -> str:
    """分类错误，返回友好提示"""
    import traceback
    traceback.print_exc()

    exc_type, exc_val, _ = sys.exc_info()
    msg = str(exc_val) if exc_val else ""

    if exc_type and "openai" in str(exc_type.__module__):
        if "401" in msg or "Authentication" in msg:
            return "[错误] API Key 无效，请检查 DEEPSEEK_API_KEY 是否正确"
        if "400" in msg:
            if "tool_calls" in msg and "tool messages" in msg:
                return "[错误] 消息序列格式异常（孤立的 tool_calls）。已自动清理，请重试"
            return "[错误] 模型请求参数有误，请重试"
        if "429" in msg or "Rate" in msg:
            return "[错误] API 调用频率过高，请稍后重试"
        if "Timeout" in msg:
            return "[错误] 模型响应超时，请重试"
        return f"[错误] AI 模型调用失败: {msg[:80]}"

    if isinstance(exc_val, (ConnectionError, OSError)):
        if "8000" in msg:
            return "[错误] 数据库服务连接失败，请确认 mcp_db_server 已启动"
        if "8001" in msg:
            return "[错误] 可视化服务连接失败，请确认 mcp_analysis_server 已启动"
        if "8002" in msg:
            return "[错误] 知识库服务连接失败，请确认 mcp_rag_server 已启动"
        return "[错误] 服务连接异常，请确认所有 MCP Server 已启动"

    if "max_turns" in msg or isinstance(exc_val, TimeoutError):
        return "[错误] 分析过程过于复杂，已超时终止，请简化问题后重试"

    return f"[错误] 分析过程中出现异常，请重试。\n  详情: {msg[:120]}"


async def interactive(max_history: int = MAX_HISTORY):
    """交互式命令行"""
    await ensure_all_mcp_connected()
    print("=" * 50)
    print("  多智能体数据分析系统")
    print()
    print("  输入问题开始分析，输入 quit 退出")
    print(f"  当前保留最近 {max_history} 轮对话，输入 /history N 调整")
    print()
    print("  示例：")
    print("    - 各品类销售额排行")
    print("    - 每月销售趋势如何")
    print("    - 用户等级分布情况")
    print("    - 你好（普通问题会直接回复）")
    print("    - 各城市销售额 TOP10")
    print("    - 查一下知识库里的行业数据（需已上传文档）")
    print()

    previous_result: RunResult | None = None

    while True:
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        if user_input.startswith("/history"):
            parts = user_input.split()
            if len(parts) == 2 and parts[1].isdigit():
                max_history = int(parts[1])
                print(f"已切换为保留最近 {max_history} 轮对话\n")
            else:
                print(f"当前保留最近 {max_history} 轮对话，用法: /history 5\n")
            continue

        print("\n开始分析...\n")
        try:
            run_result = await run_agent_with_retry(user_input, previous_result, max_history)
            print(run_result.final_output)
            print()
            previous_result = run_result
        except Exception:
            msg = _format_friendly_error()
            print(msg)
            print()


def _suppress_mcp_cleanup_errors():
    """
    压制 MCP SDK 的 Streamable HTTP 清理错误

    已知 bug: streamablehttp_client 在退出时 cancel_scope 跨任务冲突，
    触发 RuntimeError: Attempted to exit cancel scope in a different task
    这是 SDK 内部问题，不影响功能，仅乱眼。
    """
    _KNOWN_PATTERNS = (
        "Attempted to exit cancel scope in a different task",
        "asynchronous generator is already running",
    )

    # 压制 sys.excepthook 级别的错误
    original_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, tb):
        if any(p in str(exc_value) for p in _KNOWN_PATTERNS):
            return
        original_excepthook(exc_type, exc_value, tb)

    sys.excepthook = _excepthook

    # 压制 asyncio 事件循环级别的错误
    try:
        loop = asyncio.get_event_loop()
        original_handler = loop.get_exception_handler()

        def _loop_handler(loop_, context):
            msg = str(context.get("message", ""))
            if any(p in msg for p in _KNOWN_PATTERNS):
                return
            if original_handler:
                original_handler(loop_, context)
            else:
                loop_.default_exception_handler(context)

        loop.set_exception_handler(_loop_handler)
    except RuntimeError:
        pass  # 没有事件循环时跳过


def main():
    import argparse
    _suppress_mcp_cleanup_errors()
    parser = argparse.ArgumentParser(description="多智能体数据分析系统")
    parser.add_argument("query", nargs="*", help="分析问题（不传则进入交互模式）")
    parser.add_argument("--db-url", help="db_server URL")
    parser.add_argument("--viz-url", help="viz_server URL")
    parser.add_argument("--rag-url", help="rag_server URL")
    parser.add_argument("--calc-url", help="calc_server URL")
    parser.add_argument("--model", default="deepseek-v4-flash", help="模型名")
    parser.add_argument("--max-history", type=int, default=MAX_HISTORY,
                        help="保留最近 N 轮对话，默认 3，0 表示不保留")
    args = parser.parse_args()

    # 覆盖 MCP Server 地址
    global DB_SERVER_URL, VIZ_SERVER_URL, RAG_SERVER_URL, CALC_SERVER_URL
    global db_mcp_server, viz_mcp_server, rag_mcp_server, calc_mcp_server

    if args.db_url:
        from .config import DB_SERVER_URL as _old_db
        DB_SERVER_URL = args.db_url
        db_mcp_server = MCPServerStreamableHttp(
            name="数据库查询服务",
            params=MCPServerStreamableHttpParams(url=f"{DB_SERVER_URL}/mcp"),
        )
        db_agent.mcp_servers = [db_mcp_server]
    if args.viz_url:
        VIZ_SERVER_URL = args.viz_url
        viz_mcp_server = MCPServerStreamableHttp(
            name="数据分析可视化服务",
            params=MCPServerStreamableHttpParams(url=f"{VIZ_SERVER_URL}/mcp"),
        )
        viz_agent.mcp_servers = [viz_mcp_server]
    if args.rag_url:
        RAG_SERVER_URL = args.rag_url
        rag_mcp_server = MCPServerStreamableHttp(
            name="知识库RAG检索服务",
            params=MCPServerStreamableHttpParams(url=f"{RAG_SERVER_URL}/mcp"),
        )
        rag_agent.mcp_servers = [rag_mcp_server]
    if args.calc_url:
        CALC_SERVER_URL = args.calc_url
        calc_mcp_server = MCPServerStreamableHttp(
            name="计算器服务",
            params=MCPServerStreamableHttpParams(url=f"{CALC_SERVER_URL}/mcp"),
        )
        main_agent.mcp_servers = [calc_mcp_server]

    # 配置 DeepSeek
    try:
        setup_deepseek()
    except ValueError as e:
        print(f"[错误] {e}")
        print("  设置: set DEEPSEEK_API_KEY=sk-xxx")
        return

    enable_progress()

    # 设置模型
    main_agent.model = args.model
    db_agent.model = args.model
    viz_agent.model = args.model
    rag_agent.model = args.model

    if args.query:
        query = " ".join(args.query)
        print(f"[查询] {query}\n")
        run_result = asyncio.run(run_agent_with_retry(query, max_history=args.max_history))
        print(run_result.final_output)
    else:
        asyncio.run(interactive(max_history=args.max_history))


if __name__ == "__main__":
    main()
