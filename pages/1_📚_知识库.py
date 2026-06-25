"""
📚 知识库管理
上传、删除、查看知识库文档
"""
import streamlit as st
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.utils import (
    run_async, call_mcp_tool, list_mcp_tools,
    get_knowledge_raw_dir, RAG_SERVER_URL,
)

st.set_page_config(page_title="知识库管理", page_icon="📚", layout="wide")

# ── Session State ──
st.session_state.setdefault("kb_refresh", 0)

# ── 工具函数 ──

def refresh():
    st.session_state.kb_refresh += 1


def parse_mcp_result(result) -> str:
    """从 MCP 调用结果中提取文本内容"""
    if hasattr(result, "content") and result.content:
        for c in result.content:
            if hasattr(c, "text"):
                return c.text
            if isinstance(c, dict) and "text" in c:
                return c["text"]
    return str(result)


def is_error_msg(text: str) -> bool:
    """检测 MCP 工具返回的文本是否包含错误"""
    error_headers = ["## 错误", "## 解析失败", "## 索引失败", "## 检索出错", "## 请求受限"]
    for h in error_headers:
        if text.startswith(h):
            return True
    # 也检查 Supabase 不可用
    if "Supabase 不可用" in text:
        return True
    return False


def show_tool_result(msg: str):
    """根据 MCP 工具返回内容显示成功或错误"""
    if is_error_msg(msg):
        st.error(msg[:500])
    else:
        st.success(msg[:500])


def parse_doc_table(markdown_text: str) -> list[dict]:
    """从 markdown 表格中解析文档列表"""
    docs = []
    lines = markdown_text.strip().split("\n")
    header_found = False
    for line in lines:
        if line.startswith("| ---"):
            header_found = True
            continue
        if header_found and line.startswith("|"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 6:
                docs.append({
                    "doc_id": parts[0],
                    "filename": parts[1],
                    "format": parts[2],
                    "chunks": parts[3],
                    "size": parts[4],
                    "time": parts[5],
                })
            elif len(parts) >= 2:
                docs.append({
                    "doc_id": parts[0],
                    "filename": parts[1],
                    "format": parts[2] if len(parts) > 2 else "",
                    "chunks": parts[3] if len(parts) > 3 else "",
                    "size": parts[4] if len(parts) > 4 else "",
                    "time": parts[5] if len(parts) > 5 else "",
                })
    return docs


# ============================================================
# Supabase 状态提示（常见故障）
# ============================================================

st.title("📚 知识库管理")
st.caption("管理知识库文档：上传、索引、删除")

# 检查 Supabase 配置，给出提示
supabase_url = os.getenv("SUPABASE_URL", "")
supabase_key = os.getenv("SUPABASE_KEY", "")
if not supabase_url or not supabase_key:
    st.warning(
        "⚠️ **Supabase 未配置**\n\n"
        "知识库需要 Supabase（pgvector）存储向量索引。请配置 `.env` 文件：\n"
        "```\nSUPABASE_URL=https://your-project.supabase.co\nSUPABASE_KEY=your-anon-key\n```\n"
        "并在 Supabase SQL Editor 中执行 `supabase_migration.sql` 创建表结构。",
        icon="⚠️",
    )

# ============================================================
# UI
# ============================================================

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("📤 上传新文档")
    supported_types = ["pdf", "docx", "xlsx", "txt", "md", "csv"]
    uploaded_file = st.file_uploader(
        "选择文件",
        type=supported_types,
        label_visibility="collapsed",
    )

    doc_type = st.selectbox(
        "文档类型",
        options=["auto", "qa", "doc"],
        format_func=lambda x: {"auto": "自动识别", "qa": "问答对（不分块）", "doc": "普通文档"}[x],
        help="QA 类型的文档不会分块，适合 FAQ 问答对",
    )

    if uploaded_file and st.button("🚀 上传并索引", type="primary", width='stretch'):
        raw_dir = get_knowledge_raw_dir()
        raw_dir.mkdir(parents=True, exist_ok=True)
        file_path = raw_dir / uploaded_file.name

        # 保存文件
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        with st.spinner(f"正在解析并索引 {uploaded_file.name}…"):
            try:
                result = call_mcp_tool(
                    RAG_SERVER_URL,
                    "upload_document",
                    {"file_path": str(file_path), "doc_type": doc_type},
                )
                msg = parse_mcp_result(result)
                show_tool_result(msg)

                # 如果是因为 Supabase 不可用导致的失败，给出引导
                if "Supabase 不可用" in msg:
                    st.info(
                        "💡 **Supabase 连接恢复后，可尝试以下操作：**\n"
                        "1. 登录 [Supabase 控制台](https://supabase.com) 检查项目状态\n"
                        "2. 如果项目已暂停，在控制台中恢复它\n"
                        "3. 如果连接超时，检查防火墙或网络设置\n"
                        "4. 修复后点击「重建全部索引」重新索引所有文档",
                        icon="💡",
                    )
                else:
                    refresh()
            except TimeoutError:
                st.error("⏱️ 上传超时，请检查 RAG 服务器状态")
            except Exception as e:
                st.error(f"上传失败：{e}")

    st.divider()
    st.subheader("🔄 重建索引")
    if st.button("重建全部索引", width='stretch', type="secondary"):
        with st.spinner("正在重建索引…"):
            try:
                result = call_mcp_tool(RAG_SERVER_URL, "reindex_all", {})
                msg = parse_mcp_result(result)
                show_tool_result(msg)
                if not is_error_msg(msg):
                    refresh()
            except Exception as e:
                st.error(f"重建失败：{e}")

with col1:
    st.subheader("📋 已索引文档")

    col_refresh, col_status = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 刷新列表", width='content'):
            refresh()
    with col_status:
        # 尝试检查 Supabase 连通性（通过调用 list_documents）
        pass

    # 获取文档列表
    try:
        result = call_mcp_tool(RAG_SERVER_URL, "list_documents", {})
        md_text = parse_mcp_result(result)
    except Exception as e:
        md_text = ""
        st.warning(f"无法连接知识库服务（{RAG_SERVER_URL}）：{e}")
        st.info("请确认 RAG MCP 服务器已启动：`python start_all_mcp.py`")

    if md_text:
        if is_error_msg(md_text):
            # 显示友好的错误引导
            if "Supabase 不可用" in md_text:
                st.error("🔌 **Supabase 不可用**")
                st.markdown("""
知识库需要 Supabase 存储向量索引，但当前无法连接。

**可能的原因和解决办法：**

| 原因 | 解决 |
|------|------|
| Supabase 项目已暂停（免费版 7 天不活跃自动暂停） | 登录 [Supabase 控制台](https://supabase.com) → 项目 Dashboard → **Restore** |
| SUPABASE_URL / SUPABASE_KEY 配置错误 | 检查 `.env` 文件中的配置是否正确 |
| 网络无法访问 Supabase | 检查网络连接和防火墙设置 |

修复后，知识库中已上传的文档会自动恢复（数据存储在 Supabase 中）。
                """)
            else:
                st.info(md_text[:500])
        elif "暂无" in md_text or "知识库为空" in md_text:
            st.info("📭 知识库为空，请在右侧上传文档。")
        else:
            docs = parse_doc_table(md_text)

            if docs:
                for i, doc in enumerate(docs):
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1, 1])
                        with c1:
                            st.markdown(f"**{doc['filename']}**  `{doc['format']}`")
                            st.caption(f"分块：{doc['chunks']}　大小：{doc['size']}　上传：{doc['time']}")
                        with c2:
                            st.caption(f"ID: {doc['doc_id'][:12]}…")
                        with c3:
                            if st.button("🗑️ 删除", key=f"del_{i}", width='stretch'):
                                try:
                                    result = call_mcp_tool(
                                        RAG_SERVER_URL,
                                        "delete_document",
                                        {"doc_id": doc["doc_id"]},
                                    )
                                    msg = parse_mcp_result(result)
                                    show_tool_result(msg)
                                    if not is_error_msg(msg):
                                        refresh()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"删除失败：{e}")

                st.caption(f"共 {len(docs)} 个文档")
            else:
                st.info("解析文档列表失败，原始输出：")
                st.code(md_text[:500])
    else:
        st.info("📭 知识库为空，请在右侧上传文档。")

# ── 页脚 ──
st.divider()
st.caption("支持的文件格式：PDF · DOCX · XLSX · TXT · MD · CSV")
