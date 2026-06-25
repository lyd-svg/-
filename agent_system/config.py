"""
配置常量
MCP Server URL、智能体模型、连接缓存
"""
import os
import time
import asyncio

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams

# 默认模型，可在 main() 中通过 --model 参数覆盖
MODEL = "deepseek-v4-flash"

# ========== MCP Server 连接（Streamable HTTP）==========

DB_SERVER_URL = os.getenv("DB_SERVER_URL", "http://localhost:8000")
VIZ_SERVER_URL = os.getenv("VIZ_SERVER_URL", "http://localhost:8001")
RAG_SERVER_URL = os.getenv("RAG_SERVER_URL", "http://localhost:8002")
CALC_SERVER_URL = os.getenv("CALC_SERVER_URL", "http://localhost:8003")

db_mcp_server = MCPServerStreamableHttp(
    name="数据库查询服务",
    params=MCPServerStreamableHttpParams(url=f"{DB_SERVER_URL}/mcp"),
)

viz_mcp_server = MCPServerStreamableHttp(
    name="数据分析可视化服务",
    params=MCPServerStreamableHttpParams(url=f"{VIZ_SERVER_URL}/mcp"),
)

rag_mcp_server = MCPServerStreamableHttp(
    name="知识库RAG检索服务",
    params=MCPServerStreamableHttpParams(url=f"{RAG_SERVER_URL}/mcp"),
)

calc_mcp_server = MCPServerStreamableHttp(
    name="计算器服务",
    params=MCPServerStreamableHttpParams(url=f"{CALC_SERVER_URL}/mcp"),
)

# 所有 MCP Server 的注册表，用于自动检查连接
_MCP_SERVERS = [
    db_mcp_server, viz_mcp_server, rag_mcp_server, calc_mcp_server,
]

# URL 映射（供 HTTP 存活检查使用，不走 MCP 协议）
_SERVER_URLS: dict[int, str] = {
    id(db_mcp_server): f"{DB_SERVER_URL}/mcp",
    id(viz_mcp_server): f"{VIZ_SERVER_URL}/mcp",
    id(rag_mcp_server): f"{RAG_SERVER_URL}/mcp",
    id(calc_mcp_server): f"{CALC_SERVER_URL}/mcp",
}

# MCP 连接检查缓存（60 秒内不重复探测）
_last_checked: dict[int, float] = {}
