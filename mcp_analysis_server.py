"""
MCP Server - 数据分析与可视化服务（兼容入口）
已重构到 mcp_servers/analysis_server/ 包
"""
from mcp_servers.analysis_server.tools import (
    mcp, get_chart_types, describe_data, visualize_data, draw_chart, health_check,
)
from mcp_servers.analysis_server.config import logger, REPORT_DIR

if __name__ == "__main__":
    import uvicorn
    port = 8001
    logger.info("报告目录：%s", REPORT_DIR)
    logger.info("启动数据分析与可视化服务（兼容入口），端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
