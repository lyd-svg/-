"""
MCP Server - 电商数据库查询服务（兼容入口）
已重构到 mcp_servers/db_server/ 包

保持向后兼容：直接从新包导入所有公共接口
"""
from mcp_servers.db_server.tools import (
    mcp, get_tables, get_schema, query_sql,
    get_sample_data, get_table_stats, get_schema_markdown,
)
from mcp_servers.db_server.config import DB_PATH, logger

if __name__ == "__main__":
    import uvicorn
    port = 8000
    logger.info("数据库文件：%s", DB_PATH or "未找到")
    logger.info("启动数据库查询服务（兼容入口），端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
