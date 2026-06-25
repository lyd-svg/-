"""
映射表
工具名 → 中文名、智能体名 → 标签、工具名 → 所属智能体
供进度追踪和路由补丁使用
"""
_FUNC_NAMES = {
    "query_sql": "执行 SQL 查询",
    "get_tables": "获取数据表列表",
    "get_schema": "获取表结构",
    "get_schema_markdown": "获取完整数据字典",
    "get_sample_data": "获取示例数据",
    "get_table_stats": "获取表统计信息",
    "visualize_data": "生成图表",
    "describe_data": "数据统计分析",
    "draw_chart": "生成静态图表",
    "get_chart_types": "获取图表类型",
    "calculate": "数学计算",
    "list_reports": "获取报告列表",
    "search_knowledge": "检索知识库",
    "web_search": "联网搜索",
    "list_documents": "获取文档列表",
    "upload_document": "上传文档索引",
    "delete_document": "删除文档",
    "reindex_all": "重建索引",
    "get_document_info": "获取文档信息",
    "health_check": "系统健康检查",
    "query_database_agent": "数据库查询智能体",
    "visualize_analysis_agent": "可视化分析智能体",
    "search_knowledge_agent": "知识库检索智能体",
}

_AGENT_LABELS = {
    "主智能体": "主智能体",
    "数据库查询智能体": "DB",
    "数据分析可视化智能体": "VIZ",
    "知识库检索智能体": "RAG",
}

_REVERSE_HANDOFF = {
    "数据库查询智能体": "query_database_agent",
    "数据分析可视化智能体": "visualize_analysis_agent",
    "知识库检索智能体": "search_knowledge_agent",
}

_TOOL_OWNER = {
    # 数据库查询智能体
    "query_sql": "数据库查询智能体",
    "get_tables": "数据库查询智能体",
    "get_schema": "数据库查询智能体",
    "get_schema_markdown": "数据库查询智能体",
    "get_sample_data": "数据库查询智能体",
    "get_table_stats": "数据库查询智能体",
    "query_database_agent": "数据库查询智能体",
    # 数据分析可视化智能体
    "visualize_data": "数据分析可视化智能体",
    "describe_data": "数据分析可视化智能体",
    "draw_chart": "数据分析可视化智能体",
    "get_chart_types": "数据分析可视化智能体",
    "list_reports": "数据分析可视化智能体",
    "visualize_analysis_agent": "数据分析可视化智能体",
    # 知识库检索智能体
    "search_knowledge": "知识库检索智能体",
    "web_search": "知识库检索智能体",
    "list_documents": "知识库检索智能体",
    "upload_document": "知识库检索智能体",
    "delete_document": "知识库检索智能体",
    "reindex_all": "知识库检索智能体",
    "get_document_info": "知识库检索智能体",
    "search_knowledge_agent": "知识库检索智能体",
    # 主智能体（计算器）
    "calculate": "主智能体",
    # 健康检查
    "health_check": "数据库查询智能体",
}
