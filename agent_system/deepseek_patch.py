"""
DeepSeek 兼容性补丁
对 OpenAI Agents SDK 输出层进行 monkey-patch，
适配 DeepSeek API 的严格消息校验。
"""
import os
import re as _re

from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api

import agents.models.chatcmpl_converter as _converter_module

_original_items_to_messages = _converter_module.Converter.items_to_messages


def _clean_surrogates(value):
    """递归移除字符串中的孤立 surrogate 字符"""
    if isinstance(value, str):
        return value.encode("utf-8", errors="surrogatepass").decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {k: _clean_surrogates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_clean_surrogates(v) for v in value]
    return value


def _sanitize_chat_messages(messages: list[dict]) -> list[dict]:
    """清理 ChatCompletion 消息列表中的孤立 tool_calls。"""
    responded: set[str] = set()
    all_tool_call_ids: set[str] = set()

    for m in messages:
        role = m.get("role", "")
        if role == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                tc_id = tc.get("id", "") if isinstance(tc, dict) else ""
                if tc_id:
                    all_tool_call_ids.add(tc_id)
        elif role == "tool":
            tc_id = m.get("tool_call_id", "")
            if tc_id:
                responded.add(tc_id)

    orphan_ids = all_tool_call_ids - responded

    result = []
    for m in messages:
        role = m.get("role", "")
        if role == "assistant" and m.get("tool_calls"):
            remaining = [
                tc for tc in m["tool_calls"]
                if tc.get("id", "") not in orphan_ids
            ]
            if len(remaining) != len(m["tool_calls"]):
                if remaining:
                    m = {**m, "tool_calls": remaining}
                else:
                    content = m.get("content") or None
                    if content is None:
                        content = "[已清理孤立的工具调用]"
                    m = {"role": "assistant", "content": content}
        if role == "assistant":
            if "reasoning_content" not in m:
                m = {**m, "reasoning_content": ""}
            if m.get("content") is None and not m.get("tool_calls"):
                m = {**m, "content": ""}
        result.append(m)

    return _clean_surrogates(result)


def _patched_items_to_messages(cls, items, **kwargs):
    """包装 Converter.items_to_messages，在转换后清理 orphan tool_calls"""
    messages = _original_items_to_messages(items, **kwargs)
    return _sanitize_chat_messages(messages)


def setup_deepseek(api_key: str = None):
    """配置 DeepSeek 作为 LLM 后端"""
    key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("需要设置 DEEPSEEK_API_KEY 环境变量")

    try:
        key.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "API Key 包含中文字符！\n"
            f"  当前 key 前 20 位: {key[:20]}...\n"
            "  请将 .env 文件中的占位符替换为真实的 DeepSeek API Key\n"
            "  获取地址: https://platform.deepseek.com/api_keys"
        )

    if not getattr(setup_deepseek, "_patch_applied", False):
        _converter_module.Converter.items_to_messages = classmethod(_patched_items_to_messages)
        setup_deepseek._patch_applied = True
        print("[补丁] 已应用 tool_calls 消息配对兼容层（DeepSeek）")

    if not getattr(setup_deepseek, "_route_patch_applied", False):
        # 导入并应用路由补丁
        from .tool_routing import apply_route_patch
        apply_route_patch()
        setup_deepseek._route_patch_applied = True
        print("[补丁] 已应用 Tool 路由修正层（ModelBehaviorError → 内联修正）")

    client = AsyncOpenAI(
        api_key=key,
        base_url="https://api.deepseek.com/v1",
    )
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions")

    print("[配置] DeepSeek API 配置完成")
    print(f"  模型：deepseek-v4-flash")
    print()
