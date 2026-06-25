"""
本地向量索引管理器（ChromaDB）
数据持久化存储在本地 vector_db/ 目录，
写操作同时尝试同步到 Supabase（向后兼容旧数据）。
"""
from .config import logger, VECTOR_DB_DIR, CANDIDATE_K, get_supabase, is_supabase_available


class LocalVectorIndex:
    """基于 ChromaDB 的本地向量索引管理器"""

    def __init__(self):
        self._model = None
        self._client = None
        self._collection = None

    def _ensure_client(self):
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
            self._collection = self._client.get_or_create_collection(
                name="knowledge_vectors",
                metadata={"hnsw:space": "cosine"},
            )

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return self._model

    def add_chunks(self, chunk_ids: list[str], chunks: list[str], metadatas: list[dict]):
        """将分块向量写入本地 ChromaDB，同时尝试同步到 Supabase"""
        self._ensure_client()

        embeddings = self.model.encode(chunks, show_progress_bar=False)

        chroma_metadatas = []
        for m in metadatas:
            chroma_metadatas.append({
                "chunk_index": int(m.get("chunk_index", 0)),
                "doc_id": str(m.get("doc_id", "")),
                "filename": str(m.get("filename", "")),
                "doc_type": str(m.get("doc_type", "doc")),
                "format": str(m.get("format", "")),
            })
        self._collection.upsert(
            ids=chunk_ids,
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=chroma_metadatas,
        )

        self._try_sync_to_supabase(chunk_ids, chunks, embeddings, metadatas)

    def _try_sync_to_supabase(self, chunk_ids, chunks, embeddings, metadatas):
        if not is_supabase_available():
            return
        try:
            supabase = get_supabase()
            rows = []
            for i, cid in enumerate(chunk_ids):
                rows.append({
                    "id": cid,
                    "chunk_index": metadatas[i].get("chunk_index", 0),
                    "text": chunks[i],
                    "embedding": embeddings[i].tolist(),
                    "doc_id": metadatas[i]["doc_id"],
                    "filename": metadatas[i].get("filename", ""),
                    "doc_type": metadatas[i].get("doc_type", "doc"),
                })
            supabase.table("vector_chunks").upsert(rows).execute()
        except Exception:
            logger.debug("Supabase 不可用，向量仅存储在本地")

    def search(self, query: str, top_k: int = CANDIDATE_K) -> list[tuple[int, float, str, dict]]:
        """本地向量检索（ChromaDB 余弦相似度）"""
        self._ensure_client()

        n_total = self._collection.count()
        if n_total == 0:
            return []

        query_embedding = self.model.encode([query], show_progress_bar=False)[0].tolist()
        n_results = min(top_k, n_total)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        output = []
        if results.get("ids") and results["ids"][0]:
            for i, cid in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results.get("metadatas") else {}
                text = results["documents"][0][i] if results.get("documents") else ""
                distance = results["distances"][0][i] if results.get("distances") else 0
                similarity = 1.0 - distance
                idx = int(meta.get("chunk_index", 0))
                output.append((idx, similarity, text, meta))
        return output

    def delete_document(self, doc_id: str):
        """从 ChromaDB 删除文档的所有向量"""
        self._ensure_client()
        self._collection.delete(where={"doc_id": doc_id})
        if is_supabase_available():
            try:
                supabase = get_supabase()
                supabase.table("vector_chunks").delete().eq("doc_id", doc_id).execute()
            except Exception:
                pass

    def count(self) -> int:
        try:
            self._ensure_client()
            return self._collection.count()
        except Exception:
            return 0

    def delete_all(self):
        """清空所有向量"""
        self._ensure_client()
        try:
            self._client.delete_collection("knowledge_vectors")
        except Exception:
            pass
        self._collection = self._client.create_collection(
            name="knowledge_vectors",
            metadata={"hnsw:space": "cosine"},
        )
        if is_supabase_available():
            try:
                supabase = get_supabase()
                supabase.table("vector_chunks").delete().neq("id", "none").execute()
            except Exception:
                pass

    def get_chunk_indices_by_doc_id(self, doc_id: str) -> list[int]:
        """获取文档的所有分块索引（用于 BM25 删除）"""
        self._ensure_client()
        results = self._collection.get(where={"doc_id": doc_id})
        indices = []
        if results.get("metadatas"):
            for m in results["metadatas"]:
                idx = m.get("chunk_index")
                if idx is not None:
                    indices.append(int(idx))
        return indices


# 全局向量索引实例（启动时初始化）
vector_index = None
