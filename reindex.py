"""知识库重建索引脚本
用法: python reindex.py
说明: 先整理 knowledge_base/raw/ 目录，再运行此脚本
"""
import asyncio
from mcp_servers.rag_server.main import init_indexes
from mcp_servers.rag_server.tools import reindex_all as _reindex_all

init_indexes()
result = asyncio.run(_reindex_all())
print(result)
