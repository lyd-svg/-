"""
MCP Server - 安全计算器服务（兼容入口）
已重构到 mcp_servers/calculator_server/ 包
"""
import sys
from mcp_servers.calculator_server.tools import mcp, calculate, logger

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
    logger.info("启动计算器服务（兼容入口），端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
