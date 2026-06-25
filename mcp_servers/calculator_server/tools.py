"""
MCP 工具定义 — 安全计算器服务
"""
import sys
from mcp.server.fastmcp import FastMCP
from mcp_servers.common import setup_logger
from .evaluator import safe_eval

logger = setup_logger("calc_server", console_prefix="[CALC]")
mcp = FastMCP("计算器服务")


@mcp.tool()
async def calculate(expression: str) -> str:
    """
    你必须用这个工具来做所有数值计算，绝对不要自己心算。

    场景包括（不限于）：
      - 百分比/占比计算（如：A/B*100）
      - 增长率、环比、同比
      - 平均值、总和、差值
      - 复合运算（如：(sum_a - sum_b) / sum_b * 100）
      - 任何涉及数字四则运算/函数的地方

    支持：
      - 四则运算：+ - * / // %
      - 幂运算：**
      - 函数：sqrt(), abs(), round(), sin(), cos(), tan(), log(), log10(), log2(), exp(), ceil(), floor(), factorial()
      - 常量：pi, e

    示例表达式："sqrt(25) * pi + 3**2"
    :param expression: 数学表达式字符串，如 "(15000 - 12000) / 12000 * 100"
    """
    try:
        result = safe_eval(expression)
        if isinstance(result, float) and result == result:
            if result == int(result) and abs(result) < 1e15:
                return f"{expression} = {int(result)}"
            return f"{expression} = {result:.6f}"
        if isinstance(result, float) and result != result:
            return f"{expression} = NaN（结果未定义）"
        return f"{expression} = {result}"
    except ValueError as e:
        return f"## 表达式错误\n\n{str(e)}\n\n支持：四则运算、幂(**)、数学函数 sqrt/sin/cos/log/abs/round 等，常量 pi/e"
    except Exception as e:
        return f"## 计算失败\n\n表达式 '{expression}' 无法计算: {str(e)}"
