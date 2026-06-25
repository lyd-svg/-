"""
Streamlit 前端 — 多智能体数据分析系统（兼容入口）
已重构到 app/ 包

用法：
  streamlit run app.py
"""
# ── 项目根目录 ──
import sys
from pathlib import Path
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from app.config import setup_page, init_session_state
from app.ui import render_sidebar, render_chat

setup_page()
init_session_state()
render_sidebar()
render_chat()
