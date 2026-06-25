"""
数据分析诊断工具
对 JSON 数据进行全面的统计分析和图表适配评估
"""
import json
import numpy as np
import pandas as pd

from .config import logger
from .data_utils import to_df


async def describe_data(data_json: str) -> str:
    """
    数据分析诊断工具
    - 严格校验 JSON 格式
    - 数据质量检查（缺失值、重复行、异常值）
    - 图表适配分析（数值列、类别基数、画图可行性）
    - 统计描述（均值、中位数、分位数、标准差）
    - 增长率计算（如果含日期/序列列）
    - 相关性分析（多数值列）
    - 输出形式：Markdown

    :param data_json: JSON 格式数据（数组）
    """
    try:
        df = to_df(data_json)
    except Exception as e:
        return f"## 数据解析失败\n\n```\n{e}\n```\n\n支持 JSON 数组或 Markdown 表格格式。"
    if df.empty:
        return "## 数据为空"

    if df.empty:
        return "## 数据为空"

    num_df = df.select_dtypes(include=[np.number])
    cat_df = df.select_dtypes(exclude=[np.number])
    date_cols = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]

    rows = []
    rows.append(f"## 数据分析报告\n")
    rows.append(f"**数据维度**：{len(df):,} 行 × {len(df.columns)} 列\n")

    # 列信息表格
    col_info = []
    for c in df.columns:
        dtype = str(df[c].dtype)
        nunique = df[c].nunique()
        nulls = df[c].isna().sum()
        sample = df[c].dropna().iloc[0] if df[c].notna().sum() > 0 else "—"
        if isinstance(sample, str) and len(sample) > 30:
            sample = sample[:30] + "…"
        col_info.append(f"| {c} | {dtype} | {nunique:,} | {nulls:,} | {sample} |")
    col_headers = "| 列名 | 类型 | 不同值数 | 缺失数 | 样例 |\n| --- | --- | --- | --- | --- |\n"
    rows.append(f"### 列信息\n\n{col_headers}{''.join(col_info)}\n")

    # 数据质量检查
    quality_warnings = []
    null_counts = df.isnull().sum()
    null_cols = null_counts[null_counts > 0]
    if not null_cols.empty:
        for col, cnt in null_cols.items():
            pct = cnt / len(df) * 100
            quality_warnings.append(f"- ⚠ **{col}**：{cnt:,} 个缺失 ({pct:.1f}%)")
        if null_counts.max() / len(df) > 0.5:
            quality_warnings.append("- 🔴 **警告**：存在缺失超过 50% 的列，画图前建议清洗")

    dups = df.duplicated().sum()
    if dups > 0:
        quality_warnings.append(f"- ⚠ 重复行：{dups:,} 行 ({dups/len(df)*100:.1f}%)")

    for col in num_df.columns:
        vals = df[col].dropna()
        if len(vals) >= 6:
            z = (vals - vals.mean()).abs() / vals.std()
            outliers = (z > 3).sum()
            if outliers > 0:
                quality_warnings.append(f"- ⚠ **{col}**：{outliers} 个异常值 (Z>3)")

    for col in df.columns:
        if df[col].nunique() <= 1:
            quality_warnings.append(f"- ⚠ **{col}**：常数列（仅 {df[col].nunique()} 个不同值），画图无意义")

    if quality_warnings:
        rows.append("### 数据质量问题\n" + "\n".join(quality_warnings) + "\n")
    else:
        rows.append("### 数据质量问题\n\n✅ 数据质量良好，未发现明显问题\n")

    # 图表适配分析
    chart_advice = []
    if num_df.empty:
        chart_advice.append("- 🔴 没有数值列，无法生成图表")
    else:
        chart_advice.append(f"- ✅ {len(num_df.columns)} 个数值列可用作 Y 轴")

    if cat_df.empty and date_cols:
        chart_advice.append("- ✅ 含日期列，适合画**折线图**（趋势分析）")
    elif cat_df.empty and not date_cols:
        chart_advice.append("- ⚠ 无非数值列，可尝试**散点图**（需两个数值列）")
    else:
        for c in cat_df.columns:
            n = df[c].nunique()
            if n <= 6:
                chart_advice.append(f"- ✅ **{c}**（{n} 类）适合**柱状图**或**扇形图**")
            elif n <= 20:
                chart_advice.append(f"- ✅ **{c}**（{n} 类）适合**柱状图**")
            else:
                chart_advice.append(f"- ⚠ **{c}** 类别过多（{n} 类），柱状图会拥挤，建议先聚合")

    if len(df) < 3:
        chart_advice.append("- ⚠ 数据点过少（<3），图表可能缺乏可读性")

    rows.append("### 图表适配建议\n" + "\n".join(chart_advice) + "\n")

    # 统计描述
    if not num_df.empty:
        desc = num_df.describe().T
        desc["count"] = desc["count"].map(lambda x: f"{x:.0f}")
        median_series = num_df.median()
        desc["中位数"] = median_series.values
        desc = desc[["count", "mean", "中位数", "std", "min", "25%", "50%", "75%", "max"]]
        rows.append("### 数值列统计\n")
        rows.append(desc.to_markdown(numalign="left", floatfmt=".4f"))
        rows.append("")

    # 类别列分布
    if not cat_df.empty:
        rows.append("### 类别列分布\n")
        for col in cat_df.columns:
            vc = df[col].value_counts().head(10)
            if vc.empty:
                continue
            top_val = vc.index[0]
            top_pct = vc.iloc[0] / len(df) * 100
            rows.append(f"- **{col}**：共 {df[col].nunique()} 类，最多「{top_val}」({top_pct:.1f}%)")
            top5 = vc.head(5).reset_index()
            top5.columns = [col, "频数"]
            top5["占比"] = (top5["频数"] / len(df) * 100).round(1).apply(lambda x: f"{x}%")
            rows.append(f"  {top5.to_markdown(index=False, numalign='left')}")
            rows.append("")

    # 增长率分析
    if date_cols:
        dc = date_cols[0]
        for vc in num_df.columns:
            group_df = df.groupby(dc)[vc].sum().reset_index().sort_values(dc)
            if len(group_df) >= 2:
                vals = group_df[vc].astype(float)
                prev = vals.shift(1)
                growth = ((vals - prev) / prev.abs() * 100).fillna(0)
                avg_g = growth.mean()
                rows.append(f"### 增长率（{vc} 按 {dc}）\n")
                rows.append(f"- 平均增长率：{avg_g:.2f}%")
                rows.append(f"- 期数：{len(group_df)}")
                growth_table = group_df.copy()
                growth_table["增长率(%)"] = growth.round(2)
                rows.append(f"\n{growth_table.to_markdown(index=False, numalign='left', floatfmt='.2f')}\n")
                break

    # 相关性分析
    if len(num_df.columns) >= 2:
        corr = num_df.corr()
        rows.append("### 相关性矩阵\n")
        rows.append(corr.to_markdown(numalign="left", floatfmt=".4f"))
        rows.append("")
        corr_triu = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
        pairs = [(corr_triu.columns[i], corr_triu.columns[j], corr_triu.iloc[i, j])
                 for i in range(len(corr_triu)) for j in range(len(corr_triu))
                 if pd.notna(corr_triu.iloc[i, j])]
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        if pairs:
            rows.append("**最强相关对**：\n")
            for a, b, r in pairs[:3]:
                strength = "强" if abs(r) > 0.7 else ("中" if abs(r) > 0.4 else "弱")
                rows.append(f"- **{a}** ↔ **{b}**：r = {r:.4f}（{strength}相关）")
            rows.append("")

    # 画图建议
    rows.append("### 画图建议\n")
    if not num_df.empty:
        if date_cols:
            rows.append("推荐画**折线图**观察趋势。")
        elif len(num_df.columns) >= 2:
            rows.append("推荐画**散点图**观察变量关系。")
        else:
            rows.append("推荐画**柱状图**对比各类别。")
    else:
        rows.append("数据缺少数值列，无法直接画图。")

    return "\n".join(rows)
