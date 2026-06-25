"""
UI 渲染辅助函数
"""
import os
import re
import streamlit as st
from pathlib import Path

from agent_system import (
    setup_deepseek, ensure_all_mcp_connected,
    main_agent, db_agent, viz_agent, rag_agent, MODEL, _MCP_SERVERS,
)

from .config import ROOT_DIR


def init_system() -> bool:
    """初始化 DeepSeek 配置（幂等）"""
    if st.session_state.config_done:
        return True
    try:
        setup_deepseek()
        st.session_state.config_done = True
        return True
    except Exception as e:
        st.error(f"❌ 初始化失败：{e}")
        return False


def update_model(model_name: str):
    """切换所有智能体的模型"""
    if model_name != st.session_state.model:
        st.session_state.model = model_name
        main_agent.model = model_name
        db_agent.model = model_name
        viz_agent.model = model_name
        rag_agent.model = model_name


async def check_mcp_connections() -> dict[str, bool]:
    """检查所有 MCP Server 的连接状态"""
    connected = await ensure_all_mcp_connected()
    status = {}
    names = ["数据库查询服务", "可视化分析服务", "知识库RAG检索服务", "计算器服务"]
    for s in _MCP_SERVERS:
        status[s.name] = s in connected if connected else False
    return status


def render_response(response: str):
    """渲染智能体响应文本+图表。同时检测 ![]() 标记和裸路径。"""
    # 1) 处理标准 markdown 图片 ![](path)
    img_pattern = r'(!\[[^\]]*\]\([^)]+\))'
    parts = re.split(img_pattern, response)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        img_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', part)
        if img_match:
            path = img_match.group(2)
            abs_path = path if os.path.isabs(path) else str(ROOT_DIR / path)
            if os.path.exists(abs_path):
                st.image(abs_path, width='stretch')
            else:
                st.caption(f"📷 图表文件未找到：{abs_path}")
            continue

        # 2) 检测裸路径（agent 可能只输出文字路径没有 ![]()）
        chart_paths = re.findall(
            r'[^\s)]*(?:reports/charts/|reports\\charts\\)[\w\-\.]+\.png',
            part, re.IGNORECASE,
        )
        for cp in chart_paths:
            abs_cp = cp if os.path.isabs(cp) else str(ROOT_DIR / cp)
            if os.path.exists(abs_cp):
                st.image(abs_cp, width='stretch')
                part = part.replace(cp, "")
            part = part.strip()

        if part:
            st.markdown(part)
