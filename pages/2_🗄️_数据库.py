"""
🗄️ 数据库管理
上传、查看自定义数据库文件
"""
import streamlit as st
import os
import sys
from pathlib import Path
import time as time_module

ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.utils import (
    call_mcp_tool, list_mcp_tools,
    get_db_dir, DB_SERVER_URL, RAG_SERVER_URL,
)

st.set_page_config(page_title="数据库管理", page_icon="🗄️", layout="wide")

# ── Session State ──
st.session_state.setdefault("db_refresh", 0)


def refresh():
    st.session_state.db_refresh += 1


def format_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.2f} MB"


def get_db_info_from_schema(schema_text: str) -> list[str]:
    """从 schema 文本中提取表名"""
    tables = []
    for line in schema_text.split("\n"):
        line = line.strip()
        if line.startswith("## ") or line.startswith("### "):
            name = line.lstrip("#").strip()
            if name and not name.startswith("表结构"):
                tables.append(name)
    return tables


# ============================================================
# 路径
# ============================================================

# 系统内置数据库
E_COMMERCE_DB = ROOT_DIR / "ecommerce.db"
E_COMMERCE_1_DB = ROOT_DIR / "ecommerce1.db"

DB_DIR = get_db_dir()


# ============================================================
# UI
# ============================================================

st.title("🗄️ 数据库管理")
st.caption("管理数据分析使用的数据库文件")

col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("📤 上传数据库")
    uploaded_file = st.file_uploader(
        "选择数据库文件",
        type=["db", "duckdb", "sqlite", "sqlite3"],
        label_visibility="collapsed",
        help="支持 DuckDB / SQLite 格式的数据库文件（.db / .duckdb / .sqlite / .sqlite3）",
    )

    if uploaded_file:
        file_size = len(uploaded_file.getbuffer())
        st.caption(f"文件名：{uploaded_file.name}　大小：{format_size(file_size)}")

        if st.button("📥 上传到系统", type="primary", width='stretch'):
            save_path = DB_DIR / uploaded_file.name
            if save_path.exists():
                st.warning(f"文件 `{uploaded_file.name}` 已存在，将被覆盖")

            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ 上传成功：`{uploaded_file.name}`（{format_size(file_size)}）")
            refresh()

with col1:
    st.subheader("📋 可用数据库")

    # ── 系统内置数据库 ──
    st.markdown("**系统内置**")
    system_dbs = []
    for db_path in [E_COMMERCE_DB]:
        if db_path.exists():
            size = format_size(db_path.stat().st_size)
            system_dbs.append({"name": db_path.name, "size": size, "path": str(db_path)})

    for db in system_dbs:
        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            with c1:
                st.markdown(f"📀 **{db['name']}**")
                st.caption(f"大小：{db['size']}　位置：内置")
            with c2:
                st.markdown("🏷️ `当前在用`" if db['name'] == 'ecommerce.db' else "")
            with c3:
                st.button("使用", key=f"use_{db['name']}", disabled=True,
                          help="系统数据库无法切换", width='stretch')

    # ── 用户上传的数据库 ──
    st.divider()
    st.markdown("**用户上传**")
    user_dbs = []
    if DB_DIR.exists():
        for f in sorted(DB_DIR.iterdir()):
            if f.suffix.lower() in (".db", ".duckdb", ".sqlite", ".sqlite3"):
                size = format_size(f.stat().st_size)
                mtime = time_module.strftime("%Y-%m-%d %H:%M", time_module.localtime(f.stat().st_mtime))
                user_dbs.append({"name": f.name, "size": size, "path": str(f), "mtime": mtime})

    if user_dbs:
        for db in user_dbs:
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2.5, 1, 1, 1])
                with c1:
                    st.markdown(f"📁 **{db['name']}**")
                    st.caption(f"大小：{db['size']}　上传：{db['mtime']}")
                with c2:
                    st.markdown("🏷️ `当前在用`" if db['name'] == 'ecommerce.db' else "")
                with c3:
                    st.button("🔍 查看", key=f"view_{db['name']}", disabled=True,
                              help="即将支持", width='stretch')
                with c4:
                    if st.button("🗑️ 删除", key=f"del_{db['name']}", width='stretch'):
                        try:
                            os.remove(db['path'])
                            st.toast(f"已删除 `{db['name']}`")
                            refresh()
                            st.rerun()
                        except Exception as e:
                            st.error(f"删除失败：{e}")
    else:
        st.info("📭 暂无上传的数据库文件，请在右侧上传。")
        st.caption("上传后将自动出现在此列表中。数据库文件保存在 `databases/` 目录下。")

# ── 使用说明 ──
st.divider()
with st.expander("📖 使用说明"):
    st.markdown("""
### 如何使用自定义数据库

1. **上传数据库**：在右侧上传 `.db` / `.duckdb` / `.sqlite` 文件
2. **查询数据**：返回聊天页，用自然语言提问，智能体会自动探测数据库中的表
3. **切换数据库**：（即将支持）在列表中选择要使用的数据库

### 文件位置
- 系统内置数据库：`ecommerce.db`（电商示例数据，~4GB）
- 用户上传数据库：`databases/` 目录

### 支持的数据库格式
- **DuckDB** (`.db`, `.duckdb`)
- **SQLite** (`.db`, `.sqlite`, `.sqlite3`)

> ⚠️ 注意：当前系统使用内置的 ecommerce.db，上传的数据库暂不支持自动切换。
> 如需使用上传的数据库，请将文件命名为 `ecommerce.db` 替换（会覆盖原文件）。
""")

# ── 页脚 ──
st.divider()
st.caption("支持 DuckDB / SQLite 格式 · .db / .duckdb / .sqlite / .sqlite3")
