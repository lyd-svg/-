"""
实时进度处理器
展示每一次 handoff 和工具调用
"""
from agents.tracing import HandoffSpanData, FunctionSpanData
from agents.tracing.processor_interface import TracingProcessor
from agents.tracing import set_trace_processors, set_tracing_disabled

from .mappings import _FUNC_NAMES, _AGENT_LABELS, _TOOL_OWNER


class _ProgressProcessor(TracingProcessor):
    """实时进度处理器"""

    def __init__(self):
        self._current = "主智能体"
        self._step = 0

    def on_span_start(self, span):
        data = span.span_data
        if isinstance(data, HandoffSpanData):
            from_agent = data.from_agent
            to_agent = data.to_agent
            if from_agent is None and to_agent is None:
                return
            if from_agent == "主智能体" and to_agent is None:
                return
            from_label = _AGENT_LABELS.get(from_agent, from_agent or "主智能体")
            to_label = _AGENT_LABELS.get(to_agent, to_agent or "主智能体")
            print(f"  [{from_label}] → handoff → [{to_label}]")
            if to_agent:
                self._current = to_agent
            else:
                # return_to_main 没有 to_agent，切回主智能体
                self._current = "主智能体"
        elif isinstance(data, FunctionSpanData):
            owner = _TOOL_OWNER.get(data.name)
            if owner and owner != self._current:
                from_label = _AGENT_LABELS.get(self._current, self._current)
                to_label = _AGENT_LABELS.get(owner, owner)
                print(f"  [{from_label}] → handoff → [{to_label}]")
                self._current = owner
            self._step += 1
            tool_name = _FUNC_NAMES.get(data.name, data.name)
            label = _AGENT_LABELS.get(self._current, self._current)
            print(f"  [{label}]  #{self._step} 调用 {tool_name}")

    def on_span_end(self, span):
        pass

    def on_trace_start(self, trace):
        self._step = 0
        self._current = "主智能体"
        print("  --- 开始分析 ---")

    def on_trace_end(self, trace):
        print("  --- 分析结束 ---\n")

    def shutdown(self):
        pass

    def force_flush(self):
        pass


def enable_progress():
    """启用实时进度提示"""
    set_tracing_disabled(False)
    set_trace_processors([_ProgressProcessor()])
