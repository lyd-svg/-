"""
MCP 工具定义 — RAG 知识库检索服务
"""
import os
from mcp.server.fastmcp import FastMCP
from mcp_servers.common import with_rate_limit

from .config import logger, rate_limiter, RAW_DIR, DEFAULT_TOP_K, MAX_TOP_K
from .document_parser import parse_with_type, chunk_document, PARSERS
from .bm25_store import bm25_index
from .chroma_store import vector_index
from .doc_manager import (
    _get_doc_meta, _index_document, _delete_meta_entry,
    _get_chunk_info_by_doc_id, _save_local_meta,
)
from .hybrid_search import hybrid_search

mcp = FastMCP("知识库RAG检索服务")


# ========== 工具 ==========


@mcp.tool()
async def list_documents() -> str:
    """列出知识库中所有已索引的文档"""
    meta_dict = _get_doc_meta()
    if not meta_dict:
        return "## 知识库为空\n\n暂无已索引的文档，请先使用 upload_document 上传文档。"

    lines = [
        "## 知识库文档列表\n",
        "| 文档ID | 文件名 | 格式 | 分块数 | 文件大小 | 上传时间 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for doc_id, meta in meta_dict.items():
        size_kb = meta.get("file_size", 0) / 1024
        upload_time = str(meta.get("created_at", "") or "")[:19]
        lines.append(
            f"| {doc_id[:20]}... | {meta.get('filename', '')} | {meta.get('format', '')} | "
            f"{meta.get('chunk_count', 0)} | {size_kb:.1f} KB | {upload_time} |"
        )

    lines.append(
        f"\n共 **{len(meta_dict)}** 个文档，"
        f"**{vector_index.count() if vector_index else 0}** 个分块"
    )
    return "\n".join(lines)


@mcp.tool()
@with_rate_limit(rate_limiter)
async def upload_document(file_path: str, doc_type: str = "auto") -> str:
    """
    解析文档并加入知识库索引
    支持格式：PDF, DOCX, XLSX, TXT, MD, CSV

    :param file_path: 文档路径（绝对路径，或相对于 knowledge_base/raw/ 的相对路径）
    :param doc_type: auto=自动识别, qa=问答型（不分块）, doc=普通文档
    """
    if not os.path.exists(file_path):
        alt = os.path.join(RAW_DIR, file_path)
        if os.path.exists(alt):
            file_path = alt
        else:
            return f"## 错误\n\n文件不存在: {file_path}\n请将文档放入 `{RAW_DIR}` 目录后，传入完整路径。"

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in PARSERS:
        return (f"## 不支持的格式\n\n文件格式 `{ext}` 不支持。\n"
                f"支持的格式：{', '.join(PARSERS.keys())}")

    if doc_type == "qa":
        force_type = "qa"
    elif doc_type == "doc":
        force_type = "doc"
    else:
        force_type = ""

    try:
        raw_text, blocks, detected_type = parse_with_type(file_path, force_type)
    except Exception:
        logger.exception("文档解析失败: %s", file_path)
        return "## 解析失败\n\n文件解析出错，请检查文件格式是否正确、文件是否已损坏。"

    if not blocks:
        return "## 解析结果为空\n\n文档中未提取到任何文本内容，请检查文件是否包含可读文本。"

    chunks = blocks if detected_type == "qa" else chunk_document(blocks)

    try:
        doc_id = _index_document(file_path, force_type)
    except Exception:
        logger.exception("文档索引失败: %s", file_path)
        return "## 索引失败\n\n建立索引时出错，请检查文件格式和磁盘空间。"

    type_label = "问答型" if detected_type == "qa" else "文档型"
    return (f"## 文档上传成功\n\n"
            f"- **文件名**：{os.path.basename(file_path)}\n"
            f"- **文档ID**：{doc_id}\n"
            f"- **格式**：{ext}\n"
            f"- **类型**：{type_label}\n"
            f"- **分块数**：{len(chunks)}\n"
            f"- **状态**：已索引")


@mcp.tool()
@with_rate_limit(rate_limiter)
async def search_knowledge(query: str, top_k: int = DEFAULT_TOP_K) -> str:
    """
    在知识库中执行混合检索（BM25 + 向量语义搜索 + RRF 重排序）
    返回最相关的文档片段

    :param query: 搜索查询
    :param top_k: 返回结果数量，默认 5，最大 20
    """
    if vector_index is None or vector_index.count() == 0:
        return "## 知识库为空\n\n知识库中暂无已索引的文档，请先使用 upload_document 上传文档。"

    top_k = max(1, min(top_k, MAX_TOP_K))

    try:
        results = hybrid_search(query, top_k=top_k)
    except Exception:
        logger.exception("混合检索失败: query=%s", query[:100])
        return "## 检索出错\n\n知识库检索时出现内部错误，请稍后重试。"

    if not results:
        return (f"## 检索结果\n\n查询「{query}」未找到相关内容。\n"
                f"建议：1. 换一种表述方式 2. 上传相关文档后再试")

    lines = [f"## 知识库检索结果\n\n查询：{query}\n\n共找到 **{len(results)}** 条相关结果：\n"]

    for i, r in enumerate(results, 1):
        text = r["text"]
        type_tag = "📝 QA" if r.get("doc_type") == "qa" else "📄 文档"
        if len(text) > 500:
            text = text[:250] + "\n...(中间省略)...\n" + text[-200:]
        lines.append(
            f"### [{i}] {r['filename']} ({type_tag} | 相关性: {r['score']:.4f})\n"
            f"> {text}\n"
            f"--- 来源：{r['filename']}，第 {r['chunk_index']} 分块\n"
        )

    return "\n".join(lines)


@mcp.tool()
@with_rate_limit(rate_limiter)
async def web_search(query: str, top_k: int = 5) -> str:
    """
    联网搜索最新信息，获取实时/外部数据（Tavily API）

    :param query: 搜索查询
    :param top_k: 返回结果数量，默认 5，最大 10
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return ("## 联网搜索未配置\n\n"
                "请设置 Tavily API Key：\n"
                "1. 访问 https://tavily.com 注册（免费，每月 1000 次）\n"
                "2. 获取 API Key 后设置环境变量:\n\n"
                "   set TAVILY_API_KEY=your_key_here\n\n"
                "设置完成后重启本服务即可。")

    import requests

    top_k = max(1, min(top_k, 10))

    try:
        resp = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": top_k,
                "search_depth": "basic",
                "include_answer": False,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError:
        if resp.status_code in (401, 403):
            return "## 联网搜索失败\n\nAPI Key 无效，请在 Tavily 控制台检查你的 API Key。"
        return f"## 联网搜索失败\n\nHTTP {resp.status_code}，请稍后重试。"
    except Exception:
        logger.exception("联网搜索失败: query=%s", query[:100])
        return "## 联网搜索失败\n\n搜索服务暂时不可用，请稍后重试。"

    results = data.get("results", [])
    if not results:
        return f"## 联网搜索结果\n\n查询「{query}」未找到相关内容，请尝试其他关键词。"

    lines = [
        f"## 联网搜索结果\n\n查询：{query}（来源：Tavily）\n\n共找到 **{len(results)}** 条结果：\n"
    ]

    for i, r in enumerate(results, 1):
        title = r.get("title", "无标题")
        snippet = r.get("content", "")
        url = r.get("url", "")
        lines.append(f"### [{i}] {title}\n\n> {snippet}\n\n[来源链接]({url})\n")

    return "\n".join(lines)


@mcp.tool()
async def delete_document(doc_id: str) -> str:
    """
    从知识库中删除指定文档及其所有分块

    :param doc_id: 文档ID（从 list_documents 获取）
    """
    meta_dict = _get_doc_meta()
    if doc_id not in meta_dict:
        return f"## 错误\n\n文档不存在: {doc_id}\n请先使用 list_documents 查看可用的文档ID。"

    filename = meta_dict[doc_id].get("filename", "")
    try:
        indices, vi = _get_chunk_info_by_doc_id(doc_id)
        vi.delete_document(doc_id)
        bm25_index.remove_indices(indices)
        _delete_meta_entry(doc_id)
    except Exception:
        logger.exception("删除文档失败: doc_id=%s", doc_id)
        return "## 删除失败\n\n删除文档时出现内部错误，请稍后重试。"

    return (f"## 删除成功\n\n"
            f"- **文件名**：{filename}\n"
            f"- **文档ID**：{doc_id}\n"
            f"- **已移除分块**：{len(indices)} 个\n"
            f"- **状态**：已从知识库移除")


@mcp.tool()
@with_rate_limit(rate_limiter)
async def reindex_all() -> str:
    """重建所有知识库索引（从 raw 目录中的原始文件重新解析、分块、索引）"""
    raw_files = []
    for f in sorted(os.listdir(RAW_DIR)):
        ext = os.path.splitext(f)[1].lower()
        if ext in PARSERS:
            raw_files.append(os.path.join(RAW_DIR, f))

    if not raw_files:
        return "## 无可重建的文件\n\n`knowledge_base/raw/` 目录中没有支持的文档文件。"

    # 清空旧索引
    bm25_index.clear_supabase()
    if vector_index:
        vector_index.delete_all()
    _save_local_meta({})
    from .config import is_supabase_available, get_supabase
    if is_supabase_available():
        try:
            supabase = get_supabase()
            supabase.table("doc_meta").delete().neq("doc_id", "none").execute()
        except Exception:
            logger.exception("清空 Supabase 文档元数据失败")

    success = 0
    errors = []
    for fp in raw_files:
        try:
            _index_document(fp)
            success += 1
        except Exception:
            logger.exception("重建索引失败: %s", fp)
            errors.append(os.path.basename(fp))

    parts = [
        f"## 索引重建完成\n\n- **成功**：{success} 个文档\n"
        f"- **总向量数**：{vector_index.count() if vector_index else 0}\n"
        f"- **总 BM25 分块**：{len(bm25_index.chunks)}"
    ]

    if errors:
        parts.append("\n### 失败列表\n\n" + "\n".join(f"- {e}" for e in errors))

    return "\n".join(parts)


@mcp.tool()
async def get_document_info(doc_id: str) -> str:
    """
    获取指定文档的详细信息

    :param doc_id: 文档ID
    """
    meta_dict = _get_doc_meta()
    if doc_id not in meta_dict:
        return f"## 错误\n\n文档不存在: {doc_id}\n请先使用 list_documents 查看可用的文档ID。"

    m = meta_dict[doc_id]
    size_kb = m.get("file_size", 0) / 1024
    upload_time = str(m.get("created_at", "") or "")[:19]
    return (f"## 文档信息：{m.get('filename', '')}\n\n"
            f"- **文档ID**：{doc_id}\n"
            f"- **文件名**：{m.get('filename', '')}\n"
            f"- **格式**：{m.get('format', '')}\n"
            f"- **分块数**：{m.get('chunk_count', 0)}\n"
            f"- **文件大小**：{size_kb:.1f} KB\n"
            f"- **上传时间**：{upload_time}\n"
            f"- **存储位置**：{m.get('file_path', '')}")


@mcp.tool()
async def health_check() -> str:
    """
    系统健康检查
    验证 Supabase 连接、BM25/向量索引、嵌入模型是否正常
    """
    from .config import is_supabase_available as _check_supabase

    checks = []

    # 1. Supabase 连接
    if _check_supabase():
        try:
            supabase = get_supabase()
            supabase.table("doc_meta").select("count", count="exact").execute()
            checks.append(("✅ Supabase", "连接正常"))
        except Exception:
            logger.exception("Supabase 健康检查失败")
            checks.append(("❌ Supabase", "连接失败"))
    else:
        checks.append(("⚠️ Supabase", "未连接（仅使用本地存储）"))

    # 2. BM25 索引
    try:
        if bm25_index.is_ready:
            checks.append(("✅ BM25 索引", f"正常（{len(bm25_index.chunks)} 分块）"))
        else:
            checks.append(("⚠️ BM25 索引", "未就绪（请上传文档）"))
    except Exception:
        logger.exception("BM25 索引健康检查失败")
        checks.append(("❌ BM25 索引", "检查失败"))

    # 3. 向量索引
    try:
        if vector_index:
            count = vector_index.count()
            if count > 0:
                checks.append(("✅ 向量索引", f"正常（{count} 向量）"))
            else:
                checks.append(("⚠️ 向量索引", "为空（请上传文档）"))
        else:
            checks.append(("❌ 向量索引", "未初始化"))
    except Exception:
        logger.exception("向量索引健康检查失败")
        checks.append(("❌ 向量索引", "检查失败"))

    # 4. 嵌入模型
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        _ = model.encode(["test"], show_progress_bar=False)
        checks.append(("✅ 嵌入模型", "paraphrase-multilingual-MiniLM-L12-v2"))
    except Exception:
        logger.exception("嵌入模型健康检查失败")
        checks.append(("❌ 嵌入模型", "加载失败"))

    # 5. 系统信息
    all_ok = all(c[0].startswith("✅") or c[0].startswith("⚠️") for c in checks)
    status = "🟢 系统正常" if all_ok else "🔴 系统异常"

    lines = [f"## {status}\n"]
    lines.append("| 组件 | 状态 | 详情 |")
    lines.append("| --- | --- | --- |")
    for icon, detail in checks:
        lines.append(f"| {icon} | {detail.split(chr(10))[0]} |")

    return "\n".join(lines)
