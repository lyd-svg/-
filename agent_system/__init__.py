"""
多智能体编排系统 — 包导出
保持与原有 agent_system 模块的接口兼容
"""
import os
from dotenv import load_dotenv

# 在包导入时自动加载 .env 文件（cli.py 和 app 共用）
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# 配置与常量
from .config import (
    MODEL, DB_SERVER_URL, VIZ_SERVER_URL, RAG_SERVER_URL, CALC_SERVER_URL,
    db_mcp_server, viz_mcp_server, rag_mcp_server, calc_mcp_server,
    _MCP_SERVERS, _last_checked,
)

# MCP 连接管理
from .mcp_connection import ensure_mcp_connected, ensure_all_mcp_connected

# 智能体定义
from .agents import main_agent, db_agent, viz_agent, rag_agent

# Handoff 过滤器
from .handoff_filters import strip_tool_filter, _clean_input_dicts, _clean_run_items

# DeepSeek 兼容层
from .deepseek_patch import (
    setup_deepseek, _patched_items_to_messages,
    _sanitize_chat_messages, _clean_surrogates,
)

# Tool 路由补丁
from .tool_routing import _patched_process, _build_tool_hint, apply_route_patch

# 进度追踪
from .progress import _ProgressProcessor, enable_progress

# 映射表（供 app.py 使用）
from .mappings import _TOOL_OWNER, _FUNC_NAMES, _AGENT_LABELS, _REVERSE_HANDOFF

# 对话历史
from .history import MAX_HISTORY, _trim_history, _sanitize_messages

# 智能体运行
from .conversation import run_agent, run_agent_with_retry, run_agent_streamed
