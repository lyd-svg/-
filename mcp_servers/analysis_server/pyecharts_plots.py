"""
pyecharts 图表绘制函数
4 种基础图表：柱状图、折线图、饼图、散点图
"""
import pandas as pd
from pyecharts.charts import Bar, Line, Pie, Scatter
from pyecharts import options as opts
from pyecharts.globals import ThemeType

from .config import CHART_WIDTH, CHART_HEIGHT

CHART_COLORS = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
    "#86BCB6", "#8CD17D", "#B6992D", "#499894", "#D37295",
]


def _make_opts(theme=ThemeType.LIGHT):
    return opts.InitOpts(theme=theme, width=CHART_WIDTH, height=CHART_HEIGHT)


def plot_bar(df, x_col, y_col, title, **kwargs):
    x_data = df[x_col].astype(str).tolist()
    y_data = [v if pd.notna(v) else 0 for v in df[y_col]]
    chart = (
        Bar(_make_opts())
        .add_xaxis(x_data)
        .add_yaxis(y_col, y_data,
                   label_opts=opts.LabelOpts(formatter="{c}", position="top", font_size=10))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_left="center",
                                       title_textstyle_opts=opts.TextStyleOpts(font_size=16)),
            xaxis_opts=opts.AxisOpts(name=x_col,
                                      axislabel_opts=opts.LabelOpts(rotate=35, font_size=10)),
            yaxis_opts=opts.AxisOpts(name=y_col, splitline_opts=opts.SplitLineOpts(is_show=True)),
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right",
                                           feature=opts.ToolBoxFeatureOpts(
                                               save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(background_color="#fff"),
                                               data_view=opts.ToolBoxFeatureDataViewOpts(is_show=False),
                                               restore=opts.ToolBoxFeatureRestoreOpts(),
                                           )),
        )
        .set_colors(CHART_COLORS)
    )
    return chart


def plot_line(df, x_col, y_col, title, **kwargs):
    x_data = df[x_col].astype(str).tolist()
    y_data = [v if pd.notna(v) else 0 for v in df[y_col]]
    is_smooth = kwargs.get("smooth", True)
    chart = (
        Line(_make_opts())
        .add_xaxis(x_data)
        .add_yaxis(y_col, y_data,
                   is_smooth=is_smooth,
                   symbol="circle", symbol_size=8,
                   label_opts=opts.LabelOpts(formatter="{c}", position="top", font_size=10),
                   linestyle_opts=opts.LineStyleOpts(width=2),
                   itemstyle_opts=opts.ItemStyleOpts(color=CHART_COLORS[0]))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_left="center",
                                       title_textstyle_opts=opts.TextStyleOpts(font_size=16)),
            xaxis_opts=opts.AxisOpts(name=x_col,
                                      axislabel_opts=opts.LabelOpts(rotate=35, font_size=10)),
            yaxis_opts=opts.AxisOpts(name=y_col, splitline_opts=opts.SplitLineOpts(is_show=True)),
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right",
                                           feature=opts.ToolBoxFeatureOpts(
                                               save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(background_color="#fff"),
                                               data_view=opts.ToolBoxFeatureDataViewOpts(is_show=False),
                                               restore=opts.ToolBoxFeatureRestoreOpts(),
                                           )),
        )
        .set_colors(CHART_COLORS)
    )
    return chart


def plot_pie(df, x_col, y_col, title, **kwargs):
    valid = df[y_col].notna() & (df[y_col] > 0)
    df_pos = df[valid]
    if df_pos.empty:
        raise ValueError("没有正数数据，无法生成饼图")
    x_data = df_pos[x_col].astype(str).tolist()
    y_data = [float(v) for v in df_pos[y_col]]
    data_pairs = [list(z) for z in zip(x_data, y_data)]
    chart = (
        Pie(_make_opts())
        .add(y_col, data_pairs,
             radius=["35%", "60%"],
             label_opts=opts.LabelOpts(formatter="{b}: {d}%", font_size=11),
             itemstyle_opts=opts.ItemStyleOpts(border_color="#fff", border_width=1))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_left="center",
                                       title_textstyle_opts=opts.TextStyleOpts(font_size=16)),
            legend_opts=opts.LegendOpts(type_="scroll", pos_top="bottom", orient="horizontal"),
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right",
                                           feature=opts.ToolBoxFeatureOpts(
                                               save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(background_color="#fff"),
                                               data_view=opts.ToolBoxFeatureDataViewOpts(is_show=False),
                                               restore=opts.ToolBoxFeatureRestoreOpts(),
                                           )),
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(formatter="{b}: {c} ({d}%)"),
        )
        .set_colors(CHART_COLORS)
    )
    return chart


def plot_scatter(df, x_col, y_col, title, **kwargs):
    if not pd.api.types.is_numeric_dtype(df[x_col]):
        x_data = list(range(len(df)))
        x_label = "序号（" + x_col + "）"
    else:
        x_data = [float(v) if pd.notna(v) else 0 for v in df[x_col]]
        x_label = x_col
    y_data = [float(v) if pd.notna(v) else 0 for v in df[y_col]]

    chart = (
        Scatter(_make_opts())
        .add_xaxis(x_data)
        .add_yaxis(y_col, y_data,
                   symbol_size=8,
                   label_opts=opts.LabelOpts(is_show=False))
        .set_global_opts(
            title_opts=opts.TitleOpts(title=title, pos_left="center",
                                       title_textstyle_opts=opts.TextStyleOpts(font_size=16)),
            xaxis_opts=opts.AxisOpts(name=x_label, splitline_opts=opts.SplitLineOpts(is_show=True)),
            yaxis_opts=opts.AxisOpts(name=y_col, splitline_opts=opts.SplitLineOpts(is_show=True)),
            toolbox_opts=opts.ToolboxOpts(is_show=True, pos_left="right",
                                           feature=opts.ToolBoxFeatureOpts(
                                               save_as_image=opts.ToolBoxFeatureSaveAsImageOpts(background_color="#fff"),
                                               data_view=opts.ToolBoxFeatureDataViewOpts(is_show=False),
                                               restore=opts.ToolBoxFeatureRestoreOpts(),
                                           )),
        )
        .set_series_opts(
            tooltip_opts=opts.TooltipOpts(formatter="{c}"),
        )
        .set_colors(CHART_COLORS)
    )
    return chart


PLOT_FUNCS = {
    "bar": plot_bar,
    "line": plot_line,
    "pie": plot_pie,
    "scatter": plot_scatter,
}
