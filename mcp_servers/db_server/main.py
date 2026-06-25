"""
电商数据库查询服务 — 启动入口

用法：
    python -m mcp_servers.db_server.main
    或作为兼容入口：python mcp_db_server.py
"""
from .config import DB_PATH, logger

# 导入 mcp 和工具（注册到 FastMCP）
from .tools import mcp

if __name__ == "__main__":
    import uvicorn
    port = 8000
    logger.info("数据库文件：%s", DB_PATH or "未找到")
    logger.info("启动数据库查询服务，端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
