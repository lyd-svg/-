"""
数据处理工具
JSON 转 DataFrame、Markdown 表格转 DataFrame、自动识别 X/Y 列、自动选择图表类型
"""
import json
import re
import pandas as pd
import numpy as np


def _auto_convert_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """自动识别并转换数值列和日期列"""
    for col in df.columns:
        # 尝试转数值
        try:
            converted = pd.to_numeric(df[col], errors="raise")
            df[col] = converted
            continue
        except (ValueError, TypeError, KeyError):
            pass
        # 尝试转日期
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df[col] = pd.to_datetime(df[col])
        except (ValueError, TypeError):
            pass
    return df


def json_to_df(data_json: str) -> pd.DataFrame:
    """将 JSON 字符串转为 DataFrame"""
    data = json.loads(data_json)
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    df = pd.DataFrame(data)
    return _auto_convert_dtypes(df)


_MD_TABLE_RE = re.compile(
    r"^\|(.+)\|\s*$", re.MULTILINE
)


def markdown_table_to_df(md_text: str) -> pd.DataFrame | None:
    """将 Markdown 表格字符串转为 DataFrame

    支持格式：
    | 品类 | 销售额 |
    | --- | --- |
    | 手机 | 100 |
    """
    lines = md_text.strip().split("\n")
    # 找到表格起始行（以 | 开头）
    table_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
            table_lines.append(stripped)
        elif in_table:
            break  # 表格结束

    if len(table_lines) < 3:
        return None  # 至少需要表头 + 分隔行 + 数据行

    # 跳过分隔行（|---|）
    header = table_lines[0]
    data_rows = [line for line in table_lines[2:] if not re.match(r"^\|[\s\-:]+\|$", line)]

    # 解析表头
    headers = [h.strip() for h in header.strip("|").split("|")]

    # 解析数据行
    rows = []
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) == len(headers):
            rows.append(cells)

    if not rows:
        return None

    df = pd.DataFrame(rows, columns=headers)
    return _auto_convert_dtypes(df)


def to_df(data: str) -> pd.DataFrame:
    """通用数据转 DataFrame：自动识别 JSON 或 Markdown 表格"""
    # 尝试作为 JSON
    stripped = data.strip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json_to_df(data)
        except (json.JSONDecodeError, Exception):
            pass

    # 尝试作为 Markdown 表格
    df = markdown_table_to_df(data)
    if df is not None:
        return df

    # 最后尝试 CSV（逗号或制表符分隔）
    try:
        from io import StringIO
        # 检测分隔符
        if "\t" in data:
            df = pd.read_csv(StringIO(data), sep="\t")
        elif "," in data:
            df = pd.read_csv(StringIO(data), sep=",")
        else:
            df = pd.read_csv(StringIO(data), sep=None, engine="python")
        if not df.empty:
            return _auto_convert_dtypes(df)
    except Exception:
        pass

    raise ValueError(f"无法解析数据。支持 JSON 数组、Markdown 表格或 CSV 格式。")


def auto_xy(df: pd.DataFrame, x_col=None, y_col=None):
    """自动识别 x 和 y 列，返回 (x_col, y_col, error_msg)"""
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    if not x_col:
        x_col = cat_cols[0] if cat_cols else df.columns[0]
    if not y_col:
        if num_cols:
            y_col = num_cols[0]
        elif len(df.columns) > 1:
            y_col = df.columns[1]
        else:
            return x_col, None, "没有找到可用于 Y 轴的数值列，且数据列数不足"
    if x_col == y_col and len(df.columns) == 1:
        return x_col, y_col, "数据只有一列，无法同时作为 X 轴和 Y 轴"
    return x_col, y_col, None


def auto_chart_type(title: str, df: pd.DataFrame, x_col: str, y_col: str) -> str:
    """
    根据标题关键词和数据特征自动选择最佳图表类型
    返回 line / bar / scatter / pie
    """
    tl = title.lower()

    kw_map = [
        (['增长', '趋势', '变化', '走势', '环比', '同比', '上升', '下降', '波动',
          'growth', 'trend', 'change', 'over time'], 'line'),
        (['排行', '排名', '对比', '比较', '排序', '分布情况',
          'top', 'ranking', 'compare', 'rank'], 'bar'),
        (['相关', '关系', '关联', '密度', '聚集',
          'correlation', 'distribut', 'relation', 'scatter'], 'scatter'),
        (['比例', '占比', '份额', '构成', '组成', '概率',
          'proportion', 'share', 'composition', 'pie', 'rate'], 'pie'),
    ]
    for kws, ct in kw_map:
        if any(kw in tl for kw in kws):
            return ct

    if x_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[x_col]):
        return 'line'

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if x_col in num_cols and y_col in num_cols:
        return 'scatter'

    if x_col in df.columns and df[x_col].nunique() <= 6:
        return 'pie'

    return 'bar'


def auto_detect_group(df: pd.DataFrame, x_col: str, y_col: str):
    """自动检测是否适合分组画图，返回 (group_col, 是否启用分组)"""
    cat_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    candidates = [c for c in cat_cols if c != x_col]
    for c in candidates:
        n = df[c].nunique()
        if 2 <= n <= 12:
            return c, True
    return None, False


def prepare_grouped_data(df: pd.DataFrame, x_col: str, y_col: str, group_col: str):
    """将 DataFrame 按 x_col + group_col 透视，返回适合多系列画图的格式"""
    try:
        pivot = df.pivot_table(index=x_col, columns=group_col, values=y_col, aggfunc="sum")
    except Exception:
        pivot = df.groupby([x_col, group_col])[y_col].sum().unstack(fill_value=0)
    pivot.index = pivot.index.astype(str)
    pivot.columns = pivot.columns.astype(str)
    return pivot
