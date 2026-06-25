"""
MCP Server - 知识库 RAG 检索服务（兼容入口）
已重构到 mcp_servers/rag_server/ 包

保持向后兼容：直接从新包导入所有公共接口
"""
import os

# 设置 HuggingFace 镜像（模型已缓存到本地，在包加载前设置）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from mcp_servers.rag_server.tools import (
    mcp, list_documents, upload_document, search_knowledge,
    web_search, delete_document, reindex_all, get_document_info,
    health_check,
)
from mcp_servers.rag_server.config import (
    logger, KNOWLEDGE_BASE_DIR, VECTOR_DB_DIR, SUPABASE_URL,
    CHUNK_SIZE, CHUNK_OVERLAP, RRF_K,
)
from mcp_servers.rag_server.main import init_indexes

if __name__ == "__main__":
    import uvicorn

    init_indexes()

    port = 8002
    logger.info("知识库目录：%s", KNOWLEDGE_BASE_DIR)
    logger.info("向量数据库：ChromaDB (%s)", VECTOR_DB_DIR)
    logger.info("嵌入模型：paraphrase-multilingual-MiniLM-L12-v2")
    logger.info("分块大小：%d, 重叠：%d", CHUNK_SIZE, CHUNK_OVERLAP)
    logger.info("检索方式：BM25 + Vector + RRF(k=%d)", RRF_K)
    logger.info("启动 RAG MCP 服务，端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
