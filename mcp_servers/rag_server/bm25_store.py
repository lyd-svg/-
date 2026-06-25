"""
BM25 索引管理器
基于 jieba 分词 + rank-bm25，支持 Supabase 持久化
"""
import json
import threading
from .config import logger, CANDIDATE_K, get_supabase


class BM25Index:
    """BM25 索引管理器"""

    def __init__(self):
        self.chunks: list[str] = []
        self.tokenized_corpus: list[list[str]] = []
        self.bm25 = None
        self._lock = threading.Lock()

    def tokenize(self, text: str) -> list[str]:
        import jieba
        return list(jieba.cut(text))

    def add_chunks(self, new_chunks: list[str]):
        with self._lock:
            self.chunks.extend(new_chunks)
            rows = []
            for chunk in new_chunks:
                tokens = self.tokenize(chunk)
                self.tokenized_corpus.append(tokens)
                rows.append({
                    "text": chunk,
                    "tokens": json.dumps(tokens, ensure_ascii=False),
                })
            try:
                supabase = get_supabase()
                for i in range(0, len(rows), 50):
                    batch = rows[i:i + 50]
                    supabase.table("bm25_chunks").insert(batch).execute()
            except Exception:
                logger.exception("BM25 批量写入 Supabase 失败，内存索引已更新")
            self._rebuild()

    def remove_indices(self, indices: list[int]):
        with self._lock:
            try:
                supabase = get_supabase()
                for idx in sorted(indices, reverse=True):
                    supabase.table("bm25_chunks").delete().eq("chunk_index", idx).execute()
            except Exception:
                logger.exception("BM25 从 Supabase 删除分块失败")
            for idx in sorted(indices, reverse=True):
                if 0 <= idx < len(self.chunks):
                    self.chunks.pop(idx)
                    self.tokenized_corpus.pop(idx)
            self._rebuild()

    def _rebuild(self):
        from rank_bm25 import BM25Okapi
        if self.tokenized_corpus:
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int = CANDIDATE_K) -> list[tuple[int, float]]:
        if not self.bm25 or not self.chunks:
            return []
        tokenized_query = self.tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [(i, scores[i]) for i in top_indices]

    def load_from_supabase(self) -> bool:
        """从 Supabase 加载 BM25 索引到内存"""
        try:
            supabase = get_supabase()
            result = supabase.table("bm25_chunks").select("text", "tokens").order("chunk_index").execute()
            rows = result.data
            if not rows:
                return False
            with self._lock:
                self.chunks.clear()
                self.tokenized_corpus.clear()
                for row in rows:
                    self.chunks.append(row["text"])
                    tokens = row["tokens"]
                    if isinstance(tokens, str):
                        tokens = json.loads(tokens)
                    self.tokenized_corpus.append(tokens)
                self._rebuild()
            return True
        except Exception:
            logger.exception("从 Supabase 加载 BM25 索引失败")
            return False

    def clear_supabase(self):
        """清空 Supabase 中的 BM25 表"""
        try:
            supabase = get_supabase()
            supabase.table("bm25_chunks").delete().neq("chunk_index", -1).execute()
        except Exception:
            logger.exception("清空 BM25 Supabase 表失败")
        self.clear()

    @property
    def is_ready(self) -> bool:
        return self.bm25 is not None and len(self.chunks) > 0

    def clear(self):
        with self._lock:
            self.chunks.clear()
            self.tokenized_corpus.clear()
            self.bm25 = None


# 全局 BM25 索引实例
bm25_index = BM25Index()
