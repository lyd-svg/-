"""
Tool 路由补丁
当模型在某个 agent 中调用了不属于该 agent 的工具时，
将无效工具调用伪装成工具返回结果，让模型自行修正。
"""
import re as _re

from agents.exceptions import ModelBehaviorError
from agents.items import ToolCallItem, ToolCallOutputItem
from agents.run_internal.run_steps import ProcessedResponse

import agents.run_internal.turn_resolution as _turn_resolution_module

from .mappings import _TOOL_OWNER, _AGENT_LABELS, _REVERSE_HANDOFF

_original_process = _turn_resolution_module.process_model_response

_MAIN_AGENT_NAME = "主智能体"
_SUB_AGENT_NAMES = {"数据库查询智能体", "数据分析可视化智能体", "知识库检索智能体"}


def _build_tool_hint(error_msg: str, current_agent_name: str) -> str:
    """解析 ModelBehaviorError 消息，返回引导模型修正的提示"""
    m = _re.match(r"Tool (\S+) not found in agent (.+)", error_msg)
    if not m:
        return (
            f"[系统提示] 调用了当前智能体不存在的工具，"
            f"请用 return_to_main 回到主智能体后再试。"
        )
    tool_name = m.group(1)
    owner = _TOOL_OWNER.get(tool_name)

    if not owner:
        # 工具完全未知 → 一定是幻觉，强制回主智能体
        return (
            f"[系统提示] 工具 {tool_name} 不存在于任何智能体中。"
            f"请用 return_to_main 回到主智能体，由主智能体调用正确的工具。"
        )

    if current_agent_name == _MAIN_AGENT_NAME:
        # 主智能体：可以直接 handoff 到目标子智能体
        if owner != _MAIN_AGENT_NAME:
            return (
                f"[系统提示] 工具 {tool_name} 不属于主智能体，"
                f"它属于「{owner}」。请 handoff 给 {_AGENT_LABELS.get(owner, owner)}"
                f"（handoff 工具名: {_REVERSE_HANDOFF.get(owner, '')}），"
                f"到达该智能体后再调用 {tool_name}。"
            )
        return (
            f"[系统提示] 工具 {tool_name} 当前不可用，请稍后重试。"
        )

    # 子智能体：没有跨智能体 handoff 权限，必须回主智能体
    if owner != current_agent_name:
        return (
            f"[系统提示] 工具 {tool_name} 不属于当前智能体「{current_agent_name}」，"
            f"它属于「{owner}」。子智能体不能直接跨智能体调用工具。"
            f"请先使用 return_to_main 回到主智能体，"
            f"由主智能体 handoff 到 {_AGENT_LABELS.get(owner, owner)} 后再调用。"
        )
    return (
        f"[系统提示] 工具 {tool_name} 当前不可用，"
        f"请用 return_to_main 回到主智能体后再试。"
    )


def _patched_process(*, agent, all_tools, response, output_schema,
                     handoffs, existing_items=None):
    try:
        return _original_process(
            agent=agent,
            all_tools=all_tools,
            response=response,
            output_schema=output_schema,
            handoffs=handoffs,
            existing_items=existing_items,
        )
    except ModelBehaviorError as e:
        msg = str(e)
        current_agent_name = agent.name if hasattr(agent, "name") else ""
        hint = _build_tool_hint(msg, current_agent_name)
        m = _re.match(r"Tool (\S+) not found in agent (.+)", msg)
        tool_name = m.group(1) if m else "unknown"

        invalid_call = None
        for out in response.output:
            name = out.get("name") if isinstance(out, dict) else getattr(out, "name", None)
            if name == tool_name:
                invalid_call = out
                break
        if not invalid_call:
            raise

        call_id = (
            invalid_call.get("call_id", "unknown")
            if isinstance(invalid_call, dict)
            else getattr(invalid_call, "call_id", "unknown")
        )

        tool_call_item = ToolCallItem(raw_item=invalid_call, agent=agent)
        tool_output_item = ToolCallOutputItem(
            output=hint,
            raw_item={
                "call_id": call_id,
                "output": hint,
                "type": "function_call_output",
            },
            agent=agent,
        )

        print(f"  [路由] {hint}")
        return ProcessedResponse(
            new_items=[tool_call_item, tool_output_item],
            handoffs=[],
            functions=[],
            computer_actions=[],
            local_shell_calls=[],
            shell_calls=[],
            apply_patch_calls=[],
            tools_used=[tool_name],
            mcp_approval_requests=[],
            interruptions=[],
            custom_tool_calls=[],
        )


def apply_route_patch():
    """应用 Tool 路由补丁（幂等）"""
    _turn_resolution_module.process_model_response = _patched_process
