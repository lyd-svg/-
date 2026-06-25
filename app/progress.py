"""
Streamlit 流式进度追踪
通过 TracingProcessor 捕获智能体事件，转为用户友好的进度消息
"""
import threading
import agent_system as _agent_mod
from agents.tracing import HandoffSpanData, FunctionSpanData
from agents.tracing.processor_interface import TracingProcessor


class _ProgressBuffer:
    """线程安全的进度消息缓冲区"""

    def __init__(self):
        self._msgs: list[str] = []
        self._lock = threading.Lock()

    def push(self, msg: str):
        with self._lock:
            self._msgs.append(msg)

    def drain(self) -> list[str]:
        with self._lock:
            items = list(self._msgs)
            self._msgs.clear()
            return items


class _StreamlitTracingProcessor(TracingProcessor):
    """将智能体追踪事件转为用户友好的进度消息"""

    _HANDOFF_MSGS = {
        "数据库查询智能体":    "🗄️ 正在查询数据库…",
        "数据分析可视化智能体": "🎨 正在生成图表…",
        "知识库检索智能体":    "📚 正在检索知识库…",
    }

    _TOOL_MSGS = {
        "query_sql":        "📊 正在查询数据…",
        "get_tables":       "📋 获取数据表…",
        "get_schema":       "📋 分析表结构…",
        "visualize_data":   "📈 正在生成图表…",
        "describe_data":    "📊 分析数据…",
        "draw_chart":       "🎨 正在绘制图表…",
        "calculate":        "🧮 正在计算…",
        "search_knowledge": "📚 正在检索知识库…",
        "web_search":       "🌐 正在联网搜索…",
        "get_chart_types":  "📊 分析图表类型…",
        "get_sample_data":  "📋 获取示例数据…",
        "upload_document":  "📄 上传文档…",
    }

    def __init__(self, buf: _ProgressBuffer):
        self._buf = buf
        self._current = "主智能体"

    def _push(self, msg: str):
        self._buf.push(msg)

    def on_span_start(self, span):
        data = span.span_data
        if isinstance(data, HandoffSpanData):
            self._on_handoff(data)
        elif isinstance(data, FunctionSpanData):
            self._on_tool(data)

    def on_span_end(self, span):
        pass

    def on_trace_start(self, trace):
        self._current = "主智能体"
        self._push("🚀 开始分析…")

    def on_trace_end(self, trace):
        self._push("✅ 分析完成")

    def shutdown(self):
        pass

    def force_flush(self):
        pass

    def _on_handoff(self, data):
        to_agent = data.to_agent
        if not to_agent:
            return
        msg = self._HANDOFF_MSGS.get(to_agent)
        if msg:
            self._push(msg)
        self._current = to_agent

    def _on_tool(self, data):
        owner = _agent_mod._TOOL_OWNER.get(data.name)
        if owner and owner != self._current:
            msg = self._HANDOFF_MSGS.get(owner)
            if msg:
                self._push(msg)
            self._current = owner

        msg = self._TOOL_MSGS.get(data.name)
        if msg:
            self._push(msg)
