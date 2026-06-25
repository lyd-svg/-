"""
MCP 工具定义 — 数据分析与可视化服务
"""
import os
import json
from uuid import uuid4
from typing import Optional
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mcp.server.fastmcp import FastMCP
from mcp_servers.common import with_rate_limit

from .config import logger, rate_limiter, CHART_DIR, CHART_TYPES, MPL_COLORS
from .data_utils import to_df, auto_xy, auto_chart_type, auto_detect_group
from .pyecharts_plots import PLOT_FUNCS as _PYE_PLOT_FUNCS
from .mpl_plots import (
    MPL_PLOT_FUNCS, VIZ_FUNCS, VIZ_AUTO_RULES,
    mpl_bar as _mpl_bar_fallback,
)

mcp = FastMCP("数据分析与可视化服务")


@mcp.tool()
async def get_chart_types() -> str:
    """获取支持的图表类型列表及说明"""
    lines = ["## 支持的图表类型\n"]
    for name, desc in CHART_TYPES.items():
        lines.append(f"- **{name}**：{desc}")
    return "\n".join(lines)


@mcp.tool()
@with_rate_limit(rate_limiter)
async def describe_data(data_json: str) -> str:
    """
    数据分析诊断工具 —— 画图前必须先调用此工具排查数据问题
    - 严格校验 JSON 格式
    - 数据质量检查（缺失值、重复行、异常值）
    - 图表适配分析
    - 统计描述
    - 增长率计算（如果含日期/序列列）
    - 相关性分析（多数值列）

    :param data_json: JSON 格式数据（数组）
    """
    from .describe import describe_data as _describe
    return await _describe(data_json)


def _plot_and_encode(df, chart_type, x_col, y_col, title, **kwargs):
    """绘制 pyecharts 图表并返回嵌入 HTML"""
    if chart_type not in _PYE_PLOT_FUNCS:
        raise ValueError(f"不支持的图表类型 '{chart_type}'")
    chart = _PYE_PLOT_FUNCS[chart_type](df, x_col, y_col, title, **kwargs)
    return chart.render_embed()


@mcp.tool()
@with_rate_limit(rate_limiter)
async def visualize_data(
    data_json: str,
    title: str = "",
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
    group_col: Optional[str] = None,
    chart_type: str = "auto",
    width: int = 12,
    height: int = 7,
) -> str:
    """
    高级可视化工具 —— 支持多系列分组画图，自动识别分组列

    支持图表类型：bar/stacked_bar/hbar/line/area

    :param data_json: JSON 数组
    :param title: 图表标题
    :param x_col: X 轴列名（自动识别）
    :param y_col: Y 轴列名（自动识别）
    :param group_col: 分组列名（自动检测）
    :param chart_type: auto/bar/stacked_bar/hbar/line/area
    :param width: 图表宽度（英寸）
    :param height: 图表高度（英寸）
    """
    try:
        df = to_df(data_json)
    except Exception as e:
        return f"## 数据解析失败\n\n```\n{e}\n```\n\n支持 JSON 数组或 Markdown 表格格式。"
    if df.empty:
        return "## 数据为空"

    x_col, y_col, err = auto_xy(df, x_col, y_col)
    if err:
        return f"## 无法确定画图列\n\n{err}"
    if x_col not in df.columns or y_col not in df.columns:
        return f"## 列名不存在\n\n可用列：{', '.join(df.columns.tolist())}"

    has_group = False
    if group_col:
        if group_col not in df.columns:
            return f"## 分组列 '{group_col}' 不存在\n\n可用列：{', '.join(df.columns.tolist())}"
        has_group = True
    else:
        detected_group, has_group = auto_detect_group(df, x_col, y_col)
        if has_group:
            group_col = detected_group
        if not has_group:
            return await draw_chart(data_json, title=title, x_col=x_col, y_col=y_col,
                                    chart_type=chart_type, width=width, height=height)

    if chart_type == "auto":
        tl = title.lower()
        for kws, ct in VIZ_AUTO_RULES:
            if any(kw in tl for kw in kws):
                chart_type = ct
                break
        if chart_type == "auto":
            if x_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[x_col]):
                chart_type = "line"
            elif df[group_col].nunique() <= 4:
                chart_type = "bar"
            else:
                chart_type = "line"

    if chart_type not in VIZ_FUNCS:
        return f"不支持的图表类型 '{chart_type}'，支持：{', '.join(VIZ_FUNCS.keys())}"

    if not title:
        title = f"{VIZ_FUNCS[chart_type][0]}：{y_col} by {x_col}（按 {group_col} 分组）"

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    stats_lines = []
    if y_col in num_cols:
        y_data = df[y_col].dropna()
        if len(y_data) > 0:
            stats_lines.append(f"- **{y_col}**：均值={y_data.mean():,.2f}，中位数={y_data.median():,.2f}，"
                               f"总计={y_data.sum():,.2f}")
    if has_group:
        group_counts = df[group_col].value_counts()
        stats_lines.append(f"- **{group_col}** 分组：{len(group_counts)} 组 "
                           f"（{', '.join(f'{k}:{v}' for k, v in group_counts.items())}）")

    try:
        fig, ax = plt.subplots(figsize=(width, height), facecolor='white')
        _, draw_func = VIZ_FUNCS[chart_type]
        try:
            if chart_type in ("hbar",):
                draw_func(ax, df, x_col, y_col)
            else:
                draw_func(ax, df, x_col, y_col, group_col)
        except Exception as e:
            plt.close(fig)
            return await draw_chart(data_json, title=f"{title}（降级）", x_col=x_col, y_col=y_col,
                                    chart_type="bar", width=width, height=height)

        ax.set_title(title, fontsize=14, pad=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        fig.tight_layout()

        chart_id = uuid4().hex
        png_name = f"chart_{chart_id}.png"
        png_path = os.path.join(CHART_DIR, png_name)
        plt.savefig(png_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
    except Exception as e:
        plt.close('all')
        return f"## 画图失败\n\n```\n{e}\n```"

    preview = df.head(10).to_markdown(index=False, numalign="left")
    chart_label = VIZ_FUNCS[chart_type][0]

    return (f"## {title}\n\n"
            f"**数据维度**：{len(df):,} 行 × {len(df.columns)} 列\n"
            f"**图表类型**：{chart_label}\n"
            f"**X 轴**：{x_col}　**Y 轴**：{y_col}"
            + (f"　**分组**：{group_col}" if has_group else "") + "\n\n"
            f"![{title}]({png_path})\n\n"
            f"### 统计摘要\n"
            + "\n".join(stats_lines) + "\n\n"
            f"### 数据预览（前 10 行）\n\n{preview}")


@mcp.tool()
@with_rate_limit(rate_limiter)
async def draw_chart(
    data_json: str,
    title: str = "",
    x_col: Optional[str] = None,
    y_col: Optional[str] = None,
    chart_type: str = "auto",
    width: int = 10,
    height: int = 6,
) -> str:
    """
    根据诊断过的数据生成静态统计图表（matplotlib）
    建议先调用 describe_data 诊断数据质量后再用此工具画图。

    自动选型规则：
      - 增长/趋势/变化 → 折线图
      - 排行/排名/对比 → 柱状图
      - 分布/相关/关系 → 散点图
      - 占比/比例/份额 → 扇形图

    :param data_json: JSON 数组
    :param title: 图表标题
    :param x_col: X 轴列名
    :param y_col: Y 轴列名
    :param chart_type: auto/bar/line/scatter/pie
    :param width: 图表宽度（英寸）
    :param height: 图表高度（英寸）
    """
    try:
        df = to_df(data_json)
    except Exception as e:
        return f"## 数据解析失败\n\n```\n{e}\n```\n\n支持 JSON 数组或 Markdown 表格格式。"
    if df.empty:
        return "## 数据为空"

    x_col, y_col, err = auto_xy(df, x_col, y_col)
    if err:
        return f"## 无法确定画图列\n\n{err}"
    if x_col not in df.columns or y_col not in df.columns:
        return f"## 列名不存在\n\n可用列：{', '.join(df.columns.tolist())}"

    if chart_type not in ("auto", "bar", "line", "scatter", "pie"):
        return f"不支持的图表类型 '{chart_type}'，支持：auto/bar/line/scatter/pie"
    if chart_type == "auto":
        chart_type = auto_chart_type(title or f"{y_col}分析", df, x_col, y_col)

    if not title:
        title = f"{chart_type}：{y_col} by {x_col}"

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    stats_lines = []
    if y_col in num_cols:
        y_data = df[y_col].dropna()
        if len(y_data) > 0:
            stats_lines.append(f"- **{y_col}**：均值={y_data.mean():,.2f}，中位数={y_data.median():,.2f}，"
                               f"最大={y_data.max():,.2f}，最小={y_data.min():,.2f}，"
                               f"总计={y_data.sum():,.2f}")

    try:
        fig, ax = plt.subplots(figsize=(width, height), facecolor='white')
        draw_func = MPL_PLOT_FUNCS.get(chart_type)
        if not draw_func:
            return f"不支持的图表类型：{chart_type}"

        try:
            draw_func(ax, df, x_col, y_col)
        except Exception:
            _mpl_bar_fallback(ax, df, x_col, y_col)
            chart_type = "bar"

        ax.set_title(title, fontsize=14, pad=12, fontweight='bold')
        fig.tight_layout()

        chart_id = uuid4().hex
        png_name = f"chart_{chart_id}.png"
        png_path = os.path.join(CHART_DIR, png_name)
        plt.savefig(png_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close(fig)
    except Exception as e:
        plt.close('all')
        return f"## 画图失败\n\n```\n{e}\n```"

    preview = df.head(10).to_markdown(index=False, numalign="left")

    return (f"## {title}\n\n"
            f"**数据维度**：{len(df):,} 行 × {len(df.columns)} 列\n"
            f"**图表类型**：{chart_type}\n"
            f"**X 轴**：{x_col}　**Y 轴**：{y_col}\n\n"
            f"![{title}]({png_path})\n\n"
            f"### 统计摘要\n"
            + "\n".join(stats_lines) + "\n\n"
            f"### 数据预览（前 10 行）\n\n{preview}")


@mcp.tool()
async def health_check() -> str:
    """系统健康检查"""
    return "## 数据分析服务状态\n\n✅ 服务运行正常"
