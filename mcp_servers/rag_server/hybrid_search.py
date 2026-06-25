"""
混合检索：BM25 + 向量检索 + RRF 融合重排序
"""
from .config import logger, RRF_K, CANDIDATE_K, DEFAULT_TOP_K
from .bm25_store import bm25_index
from .chroma_store import vector_index


def hybrid_search(query: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    BM25 + 向量混合检索 + RRF 重排序
    返回 [{"chunk_index", "text", "score", "doc_id", "filename"}, ...]
    """
    vi = vector_index
    if vi is None or vi.count() == 0:
        return []

    bm25_results = bm25_index.search(query, top_k=CANDIDATE_K)
    vector_results = vi.search(query, top_k=CANDIDATE_K)

    if not bm25_results and not vector_results:
        return []

    # RRF 融合
    rrf_scores: dict[int, float] = {}
    for rank, (idx, score) in enumerate(bm25_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (RRF_K + rank)

    for rank, (idx, score, text, meta) in enumerate(vector_results):
        rrf_scores[idx] = rrf_scores.get(idx, 0) + 1.0 / (RRF_K + rank)

    sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

    # 构建向量索引的 chunk_index -> (text, meta) 映射
    vec_map = {}
    for idx, score, text, meta in vector_results:
        if idx not in vec_map:
            vec_map[idx] = (text, meta)

    final = []
    for chunk_idx, rrf_score in sorted_results[:top_k]:
        text = bm25_index.chunks[chunk_idx] if chunk_idx < len(bm25_index.chunks) else ""
        meta = vec_map.get(chunk_idx, ({}, {}))[1] if chunk_idx in vec_map else {}
        doc_type = meta.get("doc_type", "doc")
        final.append({
            "chunk_index": chunk_idx,
            "text": text[:2000],
            "score": round(rrf_score, 4),
            "doc_id": meta.get("doc_id", "unknown"),
            "filename": meta.get("filename", "unknown"),
            "doc_type": doc_type,
        })

    return final
