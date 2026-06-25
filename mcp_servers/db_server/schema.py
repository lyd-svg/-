"""
数据库 Schema 构建
从 DuckDB 系统表动态加载表结构、注释和关系
"""
from .config import get_connection, logger

# ========== 表元数据 ==========

TABLE_COMMENTS = {
    "orders": "订单表 —— 记录所有订单信息",
    "users": "用户表 —— 系统注册用户信息",
    "products": "商品表 —— 商品目录及价格",
    "categories": "商品分类表 —— 商品所属分类",
    "reviews": "商品评价表 —— 用户对订单商品的评价和评分",
    "inventory": "库存变动记录表 —— 商品库存变化历史",
}

COMMON_RELATIONS = [
    (("orders", "users"), "订单 → 用户"),
    (("orders", "products"), "订单 → 商品"),
    (("reviews", "orders"), "评价 → 订单"),
    (("reviews", "products"), "评价 → 商品"),
    (("reviews", "users"), "评价 → 用户"),
    (("products", "categories"), "商品 → 分类"),
    (("inventory", "products"), "库存 → 商品"),
]


def build_schema(conn):
    """查询 DuckDB 系统表，构建 SCHEMA_INFO 和 TABLE_RELATIONS"""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    tables = [r[0] for r in rows]

    schema_info = {}
    table_relations = []
    for tbl in tables:
        cols = conn.execute(f'PRAGMA table_info("{tbl}")').fetchall()
        col_list = []
        for c in cols:
            name = c[1]
            dtype = c[2]
            nullable = "NOT NULL" if c[3] else ""
            desc = ""
            col_list.append((name, dtype, nullable, desc))
        schema_info[tbl] = col_list

        # 检测外键关系
        try:
            fks = conn.execute(f"SELECT * FROM pragma_foreign_key_list('{tbl}')").fetchall()
        except Exception:
            fks = []
        for fk in fks:
            col = fk[3]
            ref_table = fk[2]
            ref_col = fk[4]
            if ref_table in tables:
                table_relations.append((f"{tbl}.{col} → {ref_table}.{ref_col}", ""))

    if not table_relations:
        # 无外键时自动推断常见关联
        for (child_table, parent_table), rel_name in COMMON_RELATIONS:
            if child_table in tables and parent_table in tables:
                table_relations.append((rel_name, ""))

    return schema_info, table_relations


# 初始化 Schema
_db_init_conn = get_connection()
if _db_init_conn:
    SCHEMA_INFO, TABLE_RELATIONS = build_schema(_db_init_conn)
else:
    SCHEMA_INFO, TABLE_RELATIONS = {}, []


def get_table_comment(table_name: str) -> str:
    """获取表的中文注释"""
    return TABLE_COMMENTS.get(table_name, f"表 {table_name}")
