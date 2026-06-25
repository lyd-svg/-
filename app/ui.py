"""
Streamlit 主界面 UI
侧边栏 + 聊天区
"""
import os
import time
import sys
import concurrent.futures
import streamlit as st
from pathlib import Path

from agent_system import (
    MODEL, MAX_HISTORY, DB_SERVER_URL, VIZ_SERVER_URL, RAG_SERVER_URL, CALC_SERVER_URL,
)

from .config import ROOT_DIR, setup_page, init_session_state
from .render import init_system, update_model, check_mcp_connections, render_response
from .async_runner import run_agent_with_progress, _AGENT_TIMEOUT


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.markdown("## ⚙️ 系统控制")
        st.divider()

        if st.button("🚀 初始化系统", width='stretch', type="primary"):
            with st.spinner("正在配置 DeepSeek API..."):
                ok = init_system()
                if ok:
                    st.success("✅ 系统初始化完成")

        if st.session_state.config_done:
            st.caption("✅ 已初始化 — 模型：{}".format(st.session_state.model))
        else:
            st.caption("⏳ 请先点击初始化按钮")

        st.divider()

        st.subheader("🤖 模型")
        model_opts = ["deepseek-v4-flash", "deepseek-chat", "deepseek-reasoner"]
        sel_model = st.selectbox(
            "选择模型",
            options=model_opts,
            index=model_opts.index(st.session_state.model)
            if st.session_state.model in model_opts else 0,
            label_visibility="collapsed",
        )
        update_model(sel_model)

        st.divider()

        st.subheader("💬 对话设置")
        max_hist = st.slider(
            "保留对话轮数",
            min_value=0, max_value=20, value=st.session_state.max_history,
            help="设置为 0 则不保留上下文",
        )
        st.session_state.max_history = max_hist

        st.divider()

        with st.expander("🔌 服务状态", expanded=False):
            mcp_names = {
                "数据库查询服务": ("8000", DB_SERVER_URL),
                "可视化分析服务": ("8001", VIZ_SERVER_URL),
                "知识库RAG检索服务": ("8002", RAG_SERVER_URL),
                "计算器服务": ("8003", CALC_SERVER_URL),
            }
            for name, (port, url) in mcp_names.items():
                st.text(f"• {name}  :{port}")

            if st.button("🔄 检查连接", width='stretch'):
                with st.spinner("检查中..."):
                    try:
                        from .async_runner import run_async
                        status = run_async(check_mcp_connections())
                        for name, ok in status.items():
                            icon = "✅" if ok else "❌"
                            st.markdown(f"{icon} **{name}**")
                    except Exception as e:
                        st.error(f"连接检查失败：{e}")

        st.divider()

        if st.button("🗑️ 清空对话", width='stretch'):
            st.session_state.messages = []
            st.session_state.previous_result = None
            st.rerun()

        st.divider()

        st.subheader("⚡ 快捷提问")
        quick_questions = [
            "各品类销售额排行",
            "每月销售趋势如何",
            "用户等级分布情况",
            "各城市销售额 TOP10",
            "哪个商品评价最好",
            "查一下知识库里的行业数据",
        ]
        for q in quick_questions:
            if st.button(q, width='stretch', type="secondary"):
                st.session_state.pending_query = q
                st.rerun()


def render_chat():
    """渲染聊天主界面"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='chat-title'>", unsafe_allow_html=True)
        st.title("📊 多智能体数据分析系统")
        st.caption("基于 DeepSeek + OpenAI Agents SDK · 自然语言 → SQL / 图表 / RAG")
        st.markdown("</div>", unsafe_allow_html=True)

    st.divider()

    # 未初始化提示
    if not st.session_state.config_done:
        st.info("👈 请在左侧边栏点击 **「初始化系统」** 按钮后开始提问", icon="ℹ️")
        with st.expander("📖 系统介绍", expanded=True):
            st.markdown("""
### 能力
| 能力 | 说明 |
|------|------|
| 🗣️ **自然语言 → SQL** | 用中文提问，自动查库 |
| 📊 **自动可视化** | 结果生成图表（柱状图、折线图、饼图等） |
| 📚 **RAG 知识库** | 混合检索行业文档 |
| 🔍 **联网搜索** | 获取实时信息 |
| 🧮 **数值计算** | 安全 AST 数学求值 |

### 示例问题
```
各品类销售额排行
每月销售趋势如何
用户等级分布情况
各城市销售额 TOP10
查一下知识库里的行业数据
```
            """)

    # 聊天消息
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant":
                    render_response(msg["content"])
                else:
                    st.markdown(msg["content"])

    # 处理快捷查询
    pending = st.session_state.pop("pending_query", None)

    # 聊天输入
    user_input = st.chat_input("输入你的数据分析问题…（例：各品类销售额排行）")

    input_text = pending or user_input

    if input_text:
        st.session_state.messages.append({"role": "user", "content": input_text})

        if not st.session_state.config_done:
            err_msg = "⚠️ 系统尚未初始化，请先在左侧边栏点击「初始化系统」按钮。"
            st.session_state.messages.append({"role": "assistant", "content": err_msg})
            st.rerun()

        with st.chat_message("user"):
            st.markdown(input_text)

        with st.chat_message("assistant"):
            result_placeholder = st.empty()

            try:
                future, progress_buf = run_agent_with_progress(
                    input_text,
                    st.session_state.previous_result,
                    st.session_state.max_history,
                )

                start_time = time.monotonic()

                with result_placeholder:
                    with st.status("🤔 分析中…", expanded=True) as status:
                        while True:
                            elapsed = time.monotonic() - start_time
                            if elapsed > _AGENT_TIMEOUT:
                                raise TimeoutError(
                                    f"分析超时（超过 {_AGENT_TIMEOUT // 60} 分钟），请简化问题后重试"
                                )

                            try:
                                result = future.result(timeout=0.5)
                                for msg in progress_buf.drain():
                                    status.write(msg)
                                status.update(label="✅ 分析完成", state="complete")
                                break
                            except concurrent.futures.TimeoutError:
                                for msg in progress_buf.drain():
                                    status.write(msg)

                response = result.final_output

                result_placeholder.empty()
                with result_placeholder:
                    render_response(response)

                st.session_state.previous_result = result
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                })

            except TimeoutError as e:
                import traceback
                traceback.print_exc()
                err_msg = (
                    f"⏱️ **分析超时**\n\n"
                    f"当前问题所需步骤较多（多次数据库查询、多张图表），"
                    f"超过了 **{_AGENT_TIMEOUT // 60} 分钟** 的时间限制。\n\n"
                    f"**建议：**\n"
                    f"  1. ✂️ **拆分为子问题**，分步提问\n"
                    f"  2. 🎯 **缩小时间范围**（如只查某个月或某季度）\n"
                    f"  3. 🚀 在侧边栏切换到更快的模型\n\n"
                )
                progress_lines = progress_buf.drain()
                if progress_lines:
                    err_msg += f"**已完成的分析步骤（最后 {min(len(progress_lines), 10)} 步）：**\n"
                    for line in progress_lines[-10:]:
                        clean = line.strip()
                        if clean:
                            err_msg += f"> {clean}\n"
                    err_msg += "\n"
                err_msg += "请拆分问题后重新提问。"

                result_placeholder.empty()
                with result_placeholder:
                    st.warning(err_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                })

            except (ConnectionError, OSError) as e:
                import traceback
                traceback.print_exc()
                err_msg = (
                    f"🔌 **服务连接失败**\n\n"
                    f"`{str(e)[:150]}`\n\n"
                    f"请确认：\n"
                    f"  1. 所有 MCP Server 已启动：`python start_all_mcp.py`\n"
                    f"  2. 端口未被占用（8000/8001/8002/8003）\n"
                    f"  3. `.env` 文件配置正确\n\n"
                    f"启动服务后重试。"
                )
                result_placeholder.empty()
                with result_placeholder:
                    st.error(err_msg)

            except Exception as e:
                import traceback
                traceback.print_exc()
                msg = str(e)

                if "max_turns" in msg.lower() or "max turns" in msg.lower():
                    err_msg = (
                        f"🔄 **分析轮次超限**\n\n"
                        f"当前问题触发了过多的工具调用轮次（超过 50 轮）。\n\n"
                        f"**建议：**\n"
                        f"  - ✂️ **拆分为多个小问题**，逐次提问\n"
                        f"  - 🎯 **缩小问题范围**，减少需要查询的数据量\n"
                        f"  - 🔄 点击「清空对话」后重试"
                    )
                else:
                    err_msg = (
                        f"❌ **分析过程出现异常**\n\n"
                        f"`{msg[:150]}`\n\n"
                        f"可能的原因：\n"
                        f"  - DeepSeek API Key 无效 → 检查 `.env`\n"
                        f"  - 网络连接异常 → 检查网络后重试\n"
                        f"  - 模型暂不可用 → 在侧边栏切换其他模型\n\n"
                        f"请修复后重试。"
                    )
                result_placeholder.empty()
                with result_placeholder:
                    st.error(err_msg)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                })

            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
