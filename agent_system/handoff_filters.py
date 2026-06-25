"""
Handoff 输入过滤器
防止历史上下文中的工具名跨 agent 污染

注意：此过滤器会删除 tool 消息（工具返回数据），因此依赖数据的子智能体
（如 VIZ）不会自动看到前序 agent 的数据。数据传递依赖主智能体在 handoff
消息中显式附上。
"""
from agents.handoffs import HandoffInputData


def _clean_input_dicts(items):
    """清洗 input_history：剥离 tool_call 记录，仅保留文本消息"""
    if isinstance(items, str):
        return items
    result = []
    for item in items:
        if not isinstance(item, dict):
            result.append(item)
            continue
        role = item.get("role", "")
        if role == "tool":
            continue  # 工具返回数据由主智能体在 handoff 消息中传递
        if role == "assistant" and item.get("tool_calls"):
            content = item.get("content") or item.get("reasoning_content") or None
            entry = {"role": "assistant"}
            if content:
                entry["content"] = content
            result.append(entry)
            continue
        result.append(item)
    return result


def _clean_run_items(items):
    """清洗 pre_handoff_items：只删工具调用，保留 handoff 消息"""
    result = []
    for item in items:
        if item.type in ("tool_call_item", "tool_call_output_item"):
            continue
        result.append(item)
    return result


def strip_tool_filter(data: HandoffInputData) -> HandoffInputData:
    """Handoff 输入过滤器：删除前序 agent 的工具调用记录"""
    filtered_history = _clean_input_dicts(data.input_history)
    filtered_pre = _clean_run_items(data.pre_handoff_items)
    return HandoffInputData(
        input_history=(
            tuple(filtered_history) if isinstance(filtered_history, list) else filtered_history
        ),
        pre_handoff_items=tuple(filtered_pre),
        new_items=data.new_items,
        run_context=data.run_context,
        input_items=data.input_items,
    )
