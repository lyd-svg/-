"""
数据分析与可视化服务 — 启动入口

用法：
    python -m mcp_servers.analysis_server.main
    或作为兼容入口：python mcp_analysis_server.py
"""
from .config import logger, REPORT_DIR
from .tools import mcp

if __name__ == "__main__":
    import uvicorn
    port = 8001
    logger.info("报告目录：%s", REPORT_DIR)
    logger.info("启动数据分析与可视化服务，端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
