"""
对话历史管理
裁剪、清理消息序列
"""
from .deepseek_patch import _clean_surrogates

# 默认保留最近 8 轮对话，设为 0 表示不保留历史
MAX_HISTORY = 8


def _trim_history(messages: list[dict], max_pairs: int) -> list[dict]:
    """裁剪对话历史，保留最近 N 轮完整问答"""
    if max_pairs <= 0 or not messages:
        return []

    user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if not user_indices:
        return []

    start = user_indices[-min(max_pairs, len(user_indices))]
    return messages[start:]


def _sanitize_messages(messages: list[dict]) -> list[dict]:
    """清理消息序列：移除孤立的 tool_calls，避免 DeepSeek API 400 错误"""
    sanitized = []
    pending_tool_ids: set[str] = set()

    for m in messages:
        role = m.get("role", "")
        if role == "tool":
            tool_id = m.get("tool_call_id", "")
            pending_tool_ids.discard(tool_id)
            if sanitized and sanitized[-1].get("role") != "assistant":
                sanitized.append({"role": "assistant", "content": None})
            sanitized.append(m)
        elif role == "assistant" and m.get("tool_calls"):
            tool_ids = {tc.get("id", "") for tc in m["tool_calls"] if tc.get("id")}
            if tool_ids:
                pending_tool_ids.update(tool_ids)
                sanitized.append(m)
            else:
                sanitized.append({"role": "assistant", "content": m.get("content")})
        else:
            sanitized.append(m)

    if pending_tool_ids:
        for i in range(len(sanitized) - 1, -1, -1):
            m = sanitized[i]
            if m.get("role") == "assistant" and m.get("tool_calls"):
                remaining = [tc for tc in m["tool_calls"] if tc.get("id") not in pending_tool_ids]
                if len(remaining) != len(m["tool_calls"]):
                    if remaining:
                        sanitized[i] = {**m, "tool_calls": remaining}
                    else:
                        sanitized[i] = {"role": "assistant", "content": m.get("content") or "[已清理 tool_calls]"}

    result = []
    for m in sanitized:
        if m.get("role") == "assistant":
            if "reasoning_content" not in m:
                m = {**m, "reasoning_content": ""}
            if m.get("content") is None and not m.get("tool_calls"):
                m = {**m, "content": ""}
        result.append(m)
    return _clean_surrogates(result)
