"""
matplotlib 图表绘制函数
基础图：柱状图、折线图、散点图、饼图
高级图：分组柱状图、堆叠柱状图、横向柱状图、多折线图、面积图
"""
import pandas as pd
import numpy as np

from .config import MPL_COLORS
from .data_utils import prepare_grouped_data


# ========== 基础图表 ==========

def mpl_bar(ax, df, x_col, y_col):
    """柱状图 —— 每根柱子不同颜色"""
    x_data = df[x_col].astype(str).tolist()
    y_data = df[y_col].values
    n = len(x_data)
    colors = MPL_COLORS * (n // len(MPL_COLORS) + 1)
    bars = ax.bar(x_data, y_data, color=colors[:n], edgecolor='white', linewidth=0.6)
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.tick_params(axis='x', rotation=30)
    for bar, val in zip(bars, y_data):
        if pd.notna(val):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f'{val:.1f}', ha='center', va='bottom', fontsize=8)
    return ax


def mpl_line(ax, df, x_col, y_col):
    """折线图 —— 纯色线条 + 圆点标记"""
    x_data = df[x_col].astype(str).tolist()
    y_data = df[y_col].values
    ax.plot(x_data, y_data, color=MPL_COLORS[0], marker='o',
            linewidth=2, markersize=6, markerfacecolor=MPL_COLORS[1])
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.tick_params(axis='x', rotation=30)
    for i, v in enumerate(y_data):
        if pd.notna(v):
            ax.text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=8)
    return ax


def mpl_scatter(ax, df, x_col, y_col):
    """散点图 —— 每个点渐变色"""
    x_data = df[x_col].astype(float).values
    y_data = df[y_col].astype(float).values
    n = len(x_data)
    colors = MPL_COLORS * (n // len(MPL_COLORS) + 1)
    ax.scatter(x_data, y_data, c=colors[:n], s=60, alpha=0.75,
               edgecolors='white', linewidth=0.5)
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    return ax


def mpl_pie(ax, df, x_col, y_col):
    """扇形图 —— 每块不同颜色"""
    valid = df[y_col].notna() & (df[y_col] > 0)
    df_pos = df[valid]
    if df_pos.empty:
        raise ValueError("没有正数数据，无法生成扇形图")
    x_data = df_pos[x_col].astype(str).tolist()
    y_data = df_pos[y_col].values
    n = len(x_data)
    colors = MPL_COLORS * (n // len(MPL_COLORS) + 1)
    _, _, autotexts = ax.pie(
        y_data, labels=x_data, autopct='%1.1f%%',
        colors=colors[:n], startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1},
    )
    for t in autotexts:
        t.set_fontsize(9)
    return ax


# ========== 高级图表 ==========

def mpl_grouped_bar(ax, df, x_col, y_col, group_col):
    """分组柱状图 —— 每组不同颜色"""
    pivot = prepare_grouped_data(df, x_col, y_col, group_col)
    x = range(len(pivot.index))
    n_groups = len(pivot.columns)
    width = 0.8 / n_groups
    colors = MPL_COLORS * (n_groups // len(MPL_COLORS) + 1)
    for i, col_name in enumerate(pivot.columns):
        values = pivot[col_name].fillna(0).values
        offset = (i - (n_groups - 1) / 2) * width
        bars = ax.bar([xi + offset for xi in x], values, width,
                      label=col_name, color=colors[i],
                      edgecolor='white', linewidth=0.5)
        for bar, val in zip(bars, values):
            if pd.notna(val) and val != 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        f'{val:.1f}', ha='center', va='bottom', fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=30, ha='right')
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.legend(fontsize=8, title=group_col)
    return ax


def mpl_stacked_bar(ax, df, x_col, y_col, group_col):
    """堆叠柱状图 —— 每层不同颜色"""
    pivot = prepare_grouped_data(df, x_col, y_col, group_col)
    x = range(len(pivot.index))
    n_groups = len(pivot.columns)
    colors = MPL_COLORS * (n_groups // len(MPL_COLORS) + 1)
    bottom = [0] * len(x)
    for i, col_name in enumerate(pivot.columns):
        values = pivot[col_name].fillna(0).values
        ax.bar(x, values, bottom=bottom, label=col_name,
               color=colors[i], edgecolor='white', linewidth=0.5)
        bottom = [b + v for b, v in zip(bottom, values)]
    for i in range(len(x)):
        if bottom[i] > 0:
            ax.text(i, bottom[i], f'{bottom[i]:.0f}', ha='center', va='bottom', fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=30, ha='right')
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.legend(fontsize=8, title=group_col)
    return ax


def mpl_horizontal_bar(ax, df, x_col, y_col):
    """横向柱状图 —— 排行用，每根不同颜色"""
    sorted_df = df.sort_values(y_col, ascending=True)
    x_data = sorted_df[x_col].astype(str).tolist()
    y_data = sorted_df[y_col].values
    n = len(x_data)
    colors = MPL_COLORS * (n // len(MPL_COLORS) + 1)
    bars = ax.barh(x_data, y_data, color=colors[:n], edgecolor='white', linewidth=0.6)
    ax.set_xlabel(y_col, fontsize=10)
    ax.set_ylabel(x_col, fontsize=10)
    for bar, val in zip(bars, y_data):
        if pd.notna(val):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                    f'{val:.1f}', ha='left', va='center', fontsize=8)
    return ax


def mpl_multi_line(ax, df, x_col, y_col, group_col):
    """多折线图 —— 每组一条折线，不同颜色"""
    pivot = prepare_grouped_data(df, x_col, y_col, group_col)
    x_data = pivot.index.tolist()
    n_groups = len(pivot.columns)
    colors = MPL_COLORS * (n_groups // len(MPL_COLORS) + 1)
    for i, col_name in enumerate(pivot.columns):
        values = pivot[col_name].fillna(0).values
        ax.plot(x_data, values, color=colors[i], marker='o',
                linewidth=2, markersize=5, label=col_name)
        for j, v in enumerate(values):
            if pd.notna(v) and v != 0:
                ax.text(j, v, f'{v:.1f}', ha='center', va='bottom', fontsize=7, color=colors[i])
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.tick_params(axis='x', rotation=30)
    ax.legend(fontsize=8, title=group_col)
    return ax


def mpl_area(ax, df, x_col, y_col, group_col):
    """堆叠面积图 —— 多系列趋势"""
    pivot = prepare_grouped_data(df, x_col, y_col, group_col)
    x_data = pivot.index.tolist()
    n_groups = len(pivot.columns)
    colors = MPL_COLORS * (n_groups // len(MPL_COLORS) + 1)
    ax.stackplot(x_data,
                 [pivot[col].fillna(0).values for col in pivot.columns],
                 labels=pivot.columns.tolist(),
                 colors=colors[:n_groups], alpha=0.8,
                 edgecolor='white', linewidth=0.3)
    ax.set_xlabel(x_col, fontsize=10)
    ax.set_ylabel(y_col, fontsize=10)
    ax.tick_params(axis='x', rotation=30)
    ax.legend(fontsize=8, title=group_col, loc='upper left')
    return ax


# ========== 注册表 ==========

MPL_PLOT_FUNCS = {
    "bar": mpl_bar,
    "line": mpl_line,
    "scatter": mpl_scatter,
    "pie": mpl_pie,
}

VIZ_FUNCS = {
    "bar": ("柱状图", mpl_grouped_bar),
    "stacked_bar": ("堆叠柱状图", mpl_stacked_bar),
    "hbar": ("横向柱状图", mpl_horizontal_bar),
    "line": ("多折线图", mpl_multi_line),
    "area": ("堆叠面积图", mpl_area),
}

VIZ_AUTO_RULES = [
    (['趋势', '变化', '增长', '走势', '环比', '同比', '时间', '月份', '日期', 'year', 'month', 'trend', 'time'], 'line'),
    (['排行', '排名', 'top', 'rank', '排序'], 'hbar'),
    (['占比', '份额', '比例', 'share', 'rate', '分布'], 'stacked_bar'),
]
