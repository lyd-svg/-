"""
MCP 工具定义
数据库查询服务的所有工具函数
"""
from typing import Optional
from mcp.server.fastmcp import FastMCP

from .config import get_connection, is_db_path_available, rate_limiter, logger
from .schema import SCHEMA_INFO, TABLE_RELATIONS, get_table_comment
from .sql_validator import validate_table_name, validate_readonly_sql
from mcp_servers.common import with_rate_limit

mcp = FastMCP("电商数据库查询服务")


def _get_db_connection():
    """获取全局复用的 DuckDB 连接"""
    return get_connection()


# ========== 工具 ==========


@mcp.tool()
async def get_tables() -> str:
    """获取数据库中所有表名及说明"""
    lines = ["## 数据库表列表\n"]
    from .schema import TABLE_COMMENTS
    for table_name, comment in TABLE_COMMENTS.items():
        lines.append(f"- **{table_name}**：{comment}")
    return "\n".join(lines)


@mcp.tool()
async def get_schema(table_name: Optional[str] = None) -> str:
    """
    查询指定表的字段信息（字段名、类型、约束、说明）
    如果不传 table_name，返回所有表的字段结构
    """
    if table_name:
        tables_info = {table_name: SCHEMA_INFO.get(table_name)}
        if tables_info[table_name] is None:
            return f"表 '{table_name}' 不存在。可用表：{', '.join(SCHEMA_INFO.keys())}"
    else:
        tables_info = SCHEMA_INFO

    result_parts = []
    for tbl, cols in tables_info.items():
        if cols is None:
            continue
        comment = get_table_comment(tbl)
        header = f"## {tbl}  {comment}\n"
        rows = ["| 字段名 | 类型 | 约束 | 说明 |", "| --- | --- | --- | --- |"]
        for name, dtype, nullable, desc in cols:
            rows.append(f"| {name} | {dtype} | {nullable} | {desc} |")
        result_parts.append(header + "\n" + "\n".join(rows))

    return "\n\n".join(result_parts)


@mcp.tool()
@with_rate_limit(rate_limiter)
async def query_sql(sql: str, limit: int = 100) -> str:
    """
    对数据库执行 SQL 查询，返回 Markdown 表格结果
    :param sql: SELECT 查询语句
    :param limit: 最大返回行数，默认 100
    """
    conn = _get_db_connection()
    if conn is None:
        status = "数据库连接失败"
        if is_db_path_available():
            status += "（文件被其他程序锁定，请关闭 VS Code 中的 DuckDB 文件后重试）"
        else:
            status += "（未找到数据库文件）"
        return f"## {status}"

    try:
        validate_readonly_sql(sql)
    except ValueError as e:
        return f"## 查询被拒绝\n\n{str(e)}"

    try:
        result = conn.execute(sql).fetchdf()
        if len(result) > limit:
            result = result.head(limit)
        return result.to_markdown(index=False, numalign="left")
    except Exception:
        logger.exception("SQL 查询失败: %.200s", sql)
        return "## 查询出错\n\n请检查 SQL 语法是否正确。"


@mcp.tool()
@with_rate_limit(rate_limiter)
async def get_sample_data(table_name: str, limit: int = 5) -> str:
    """
    获取指定表的示例数据（前 N 行）
    :param table_name: 表名
    :param limit: 行数，默认 5
    """
    conn = _get_db_connection()
    if conn is None:
        status = "数据库连接失败"
        if is_db_path_available():
            status += "（文件被其他程序锁定，请关闭 VS Code 中的 DuckDB 文件后重试）"
        else:
            status += "（未找到数据库文件）"
        return f"## {status}"

    try:
        validate_table_name(table_name)
    except ValueError as e:
        return f"## 查询被拒绝\n\n{str(e)}"

    try:
        result = conn.execute(f"SELECT * FROM {table_name} LIMIT {limit}").fetchdf()
        return result.to_markdown(index=False, numalign="left")
    except Exception:
        logger.exception("示例数据查询失败: table=%s", table_name)
        return "## 查询出错\n\n查询示例数据时出现内部错误。"


@mcp.tool()
@with_rate_limit(rate_limiter)
async def get_table_stats(table_name: str) -> str:
    """
    获取指定表的数据统计（行数、每列的 distinct 值、空值数等）
    """
    conn = _get_db_connection()
    if conn is None:
        return (
            "## 数据库连接失败（需要释放文件锁才能查询统计信息）\n\n"
            "可用字段结构：\n\n" + "\n".join(
                f"| {name} | {dtype} | {nullable} | {desc} |"
                for name, dtype, nullable, desc in SCHEMA_INFO.get(table_name, [])
            )
        )

    try:
        validate_table_name(table_name)
    except ValueError as e:
        return f"## 查询被拒绝\n\n{str(e)}"

    try:
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        cols = SCHEMA_INFO.get(table_name, [])

        col_stats = []
        for col_name, col_type, _, _ in cols:
            non_null = conn.execute(
                f'SELECT COUNT(*) FROM {table_name} WHERE "{col_name}" IS NOT NULL'
            ).fetchone()[0]
            distinct = conn.execute(
                f'SELECT COUNT(DISTINCT "{col_name}") FROM {table_name}'
            ).fetchone()[0]
            null_count = row_count - non_null
            col_stats.append(
                f"| {col_name} | {col_type} | {non_null:,} | {null_count:,} | {distinct:,} |"
            )

        return (
            f"## {table_name} 统计\n\n"
            f"- 总行数：{row_count:,}\n"
            f"- 总列数：{len(cols)}\n\n"
            f"| 字段 | 类型 | 非空值 | 空值 | Distinct |\n"
            f"| --- | --- | --- | --- | --- |\n"
            + "\n".join(col_stats)
        )
    except Exception:
        logger.exception("表统计查询失败: table=%s", table_name)
        return "## 查询出错\n\n查询表统计时出现内部错误。"


@mcp.tool()
async def get_schema_markdown() -> str:
    """
    获取完整的数据库字典（Markdown），包含所有表的字段说明、类型、约束和关联关系
    """
    parts = ["# 电商数据库字典\n"]
    parts.append("## 表关系\n")
    for src, dst in TABLE_RELATIONS:
        parts.append(f"- `{src}` {dst}")
    parts.append("")

    for tbl, cols in SCHEMA_INFO.items():
        comment = get_table_comment(tbl)
        parts.append(f"## {tbl}  {comment}")
        parts.append("| 字段名 | 类型 | 约束 | 说明 |")
        parts.append("| --- | --- | --- | --- |")
        for name, dtype, nullable, desc in cols:
            parts.append(f"| {name} | {dtype} | {nullable} | {desc} |")
        parts.append("")

    return "\n".join(parts)
