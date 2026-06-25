"""
安全计算器服务 — 启动入口

用法：
    python -m mcp_servers.calculator_server.main
"""
import sys
from .tools import mcp, logger

if __name__ == "__main__":
    import uvicorn
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8003
    logger.info("启动计算器服务，端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
