"""
Streamlit 页面配置和 Session State 管理
"""
import streamlit as st
from pathlib import Path

from agent_system import MODEL, MAX_HISTORY

ROOT_DIR = Path(__file__).parent.parent


def setup_page():
    """设置页面配置和样式"""
    st.set_page_config(
        page_title="多智能体数据分析系统",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .block-container { padding-top: 1.5rem; }
        div[data-testid="stStatusWidget"] { visibility: hidden; }
        .chat-title { text-align: center; padding: 0.5rem 0; }
        .stChatMessage { border-radius: 12px; }
        div[data-testid="stChatMessage"] { border: 1px solid #e0e0e0; border-radius: 12px; padding: 0.5rem 1rem; margin-bottom: 0.5rem; }
    </style>
    """, unsafe_allow_html=True)


def init_session_state():
    """初始化 Session State"""
    _DEFAULT_STATE = {
        "messages": [],
        "previous_result": None,
        "initialized": False,
        "config_done": False,
        "model": MODEL,
        "max_history": MAX_HISTORY,
        "mcp_status": {},
    }
    for key, val in _DEFAULT_STATE.items():
        st.session_state.setdefault(key, val)
