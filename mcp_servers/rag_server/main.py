"""
RAG 知识库检索服务 — 启动入口

用法：
    python -m mcp_servers.rag_server.main
    或作为兼容入口：python mcp_rag_server.py
"""
import os
import httpx

from .config import (
    logger, SUPABASE_URL, SUPABASE_KEY, KNOWLEDGE_BASE_DIR, VECTOR_DB_DIR,
    CHUNK_SIZE, CHUNK_OVERLAP, RRF_K, set_supabase_available, is_supabase_available,
)
from .bm25_store import bm25_index
from . import chroma_store as _cs
from .doc_manager import _get_doc_meta
from .tools import mcp


def init_indexes():
    """初始化所有索引（启动时调用）"""
    from .chroma_store import LocalVectorIndex

    logger.info("正在初始化索引...")

    # 初始化本地 ChromaDB 向量索引
    vi = LocalVectorIndex()
    _cs.vector_index = vi

    try:
        local_count = vi.count()
        logger.info("本地向量索引: %d 个向量", local_count)
    except Exception:
        logger.exception("本地向量索引初始化失败")

    # 检查 Supabase 连通性
    set_supabase_available(False)
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{SUPABASE_URL}/rest/v1/", headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                })
                if resp.status_code >= 500:
                    raise ConnectionError(f"Supabase 返回 {resp.status_code}")
            set_supabase_available(True)
            logger.info("Supabase 连接正常，旧数据可用")
        except Exception as e:
            logger.warning("Supabase 连接失败 (%s)，仅使用本地存储", e)

    # 加载 BM25
    bm25_loaded = False
    if is_supabase_available():
        try:
            if bm25_index.load_from_supabase():
                logger.info("BM25 索引已加载: %d 个分块", len(bm25_index.chunks))
                bm25_loaded = True
            else:
                logger.info("BM25 索引为空（首次启动需上传文档）")
        except Exception:
            logger.exception("从 Supabase 加载 BM25 索引失败")
    if not bm25_loaded:
        logger.info("BM25 索引初始化为空，上传文档后将自动建立")

    # 加载文档元数据
    meta_dict = _get_doc_meta()
    logger.info("文档元数据: %d 个文档", len(meta_dict))

    logger.info("索引初始化完成（本地向量索引 + %s）",
                "Supabase 同步已开启" if is_supabase_available() else "仅本地模式")


if __name__ == "__main__":
    import uvicorn

    # 设置 HuggingFace 镜像（模型已缓存到本地）
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    init_indexes()

    port = 8002
    logger.info("知识库目录：%s", KNOWLEDGE_BASE_DIR)
    logger.info("向量数据库：ChromaDB (%s)", VECTOR_DB_DIR)
    logger.info("嵌入模型：paraphrase-multilingual-MiniLM-L12-v2")
    logger.info("分块大小：%d, 重叠：%d", CHUNK_SIZE, CHUNK_OVERLAP)
    logger.info("检索方式：BM25 + Vector + RRF(k=%d)", RRF_K)
    logger.info("启动 RAG MCP 服务，端口：%d", port)
    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=port)
