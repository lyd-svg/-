"""
文档管理模块
文档元数据读写、文档索引、文件复制
"""
import os
import json
import hashlib
from datetime import datetime

from .config import logger, RAW_DIR, DOC_META_PATH, get_supabase, is_supabase_available
from .document_parser import parse_with_type, chunk_document, PARSERS
from .bm25_store import bm25_index
from .chroma_store import vector_index


def _get_doc_meta() -> dict:
    """获取所有文档元数据（先查本地 JSON，再尝试 Supabase）"""
    if os.path.exists(DOC_META_PATH):
        try:
            with open(DOC_META_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.exception("读取本地文档元数据失败")

    if is_supabase_available():
        try:
            supabase = get_supabase()
            result = supabase.table("doc_meta").select("*").execute()
            meta_dict = {r["doc_id"]: r for r in result.data}
            _save_local_meta(meta_dict)
            return meta_dict
        except Exception:
            logger.exception("从 Supabase 获取文档元数据失败")

    return {}


def _save_local_meta(meta_dict: dict):
    """将文档元数据写入本地 JSON 文件"""
    os.makedirs(os.path.dirname(DOC_META_PATH), exist_ok=True)
    clean = {}
    for doc_id, entry in meta_dict.items():
        clean[doc_id] = {
            k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v)
            for k, v in entry.items()
        }
    with open(DOC_META_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def _save_meta_entry(*, doc_id: str, filename: str, doc_type: str, chunk_count: int,
                     file_path: str, file_size: int = 0, fmt: str = ""):
    """写入文档元数据（本地 JSON + 尝试同步到 Supabase）"""
    meta_dict = _get_doc_meta()
    meta_dict[doc_id] = {
        "doc_id": doc_id,
        "filename": filename,
        "doc_type": doc_type,
        "chunk_count": chunk_count,
        "file_path": file_path,
        "file_size": file_size,
        "format": fmt,
        "created_at": datetime.now().isoformat(),
    }
    _save_local_meta(meta_dict)

    if is_supabase_available():
        try:
            supabase = get_supabase()
            supabase.table("doc_meta").upsert({
                "doc_id": doc_id,
                "filename": filename,
                "doc_type": doc_type,
                "chunk_count": chunk_count,
                "file_path": file_path,
                "file_size": file_size,
                "format": fmt,
                "created_at": datetime.now().isoformat(),
            }).execute()
        except Exception:
            logger.debug("Supabase 不可用，文档元数据仅存储在本地")


def _delete_meta_entry(doc_id: str):
    """删除文档元数据（本地 + Supabase）"""
    meta_dict = _get_doc_meta()
    if doc_id in meta_dict:
        del meta_dict[doc_id]
        _save_local_meta(meta_dict)

    if is_supabase_available():
        try:
            supabase = get_supabase()
            supabase.table("doc_meta").delete().eq("doc_id", doc_id).execute()
        except Exception:
            pass


def _generate_doc_id(file_path: str) -> str:
    """根据文件路径生成唯一文档 ID"""
    raw = os.path.basename(file_path) + str(datetime.now().timestamp())
    return "doc_" + hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:12]


def _copy_to_raw(file_path: str) -> str:
    """将文档复制到知识库目录，返回目标路径"""
    basename = os.path.basename(file_path)
    dest = os.path.join(RAW_DIR, basename)
    if os.path.exists(dest) and os.path.abspath(file_path) != os.path.abspath(dest):
        name, ext = os.path.splitext(basename)
        dest = os.path.join(RAW_DIR, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")
    if os.path.abspath(file_path) != os.path.abspath(dest):
        import shutil
        shutil.copy2(file_path, dest)
    return dest


def _index_document(file_path: str, force_type: str = "") -> str:
    """解析、分块并索引单个文档，返回 doc_id"""
    global bm25_index, vector_index

    raw_text, paragraphs_or_pairs, doc_type = parse_with_type(file_path, force_type)

    if doc_type == "qa":
        chunks = paragraphs_or_pairs
    else:
        if not paragraphs_or_pairs:
            raise ValueError("文档中未提取到任何文本内容")
        chunks = chunk_document(paragraphs_or_pairs)

    if not chunks:
        raise ValueError("分块结果为空")

    stored_path = _copy_to_raw(file_path)
    filename = os.path.basename(stored_path)
    ext = os.path.splitext(filename)[1].lower()
    doc_id = _generate_doc_id(stored_path)

    chunk_ids = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        cid = f"{doc_id}_chunk_{i:04d}"
        chunk_ids.append(cid)
        metadatas.append({
            "doc_id": doc_id,
            "chunk_index": i,
            "filename": filename,
            "format": ext,
            "doc_type": doc_type,
        })

    file_size = os.path.getsize(stored_path)
    _save_meta_entry(
        doc_id=doc_id, filename=filename, doc_type=doc_type,
        chunk_count=len(chunks), file_path=stored_path,
        file_size=file_size, fmt=ext,
    )

    bm25_start = len(bm25_index.chunks)
    bm25_index.add_chunks(chunks)

    for i, meta in enumerate(metadatas):
        meta["chunk_index"] = bm25_start + i
    vector_index.add_chunks(chunk_ids, chunks, metadatas)

    return doc_id


def _get_chunk_info_by_doc_id(doc_id: str):
    """从本地向量索引获取文档分块索引列表"""
    vi = vector_index
    indices = vi.get_chunk_indices_by_doc_id(doc_id)
    return indices, vi
