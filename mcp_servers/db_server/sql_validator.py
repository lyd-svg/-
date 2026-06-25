"""
SQL 只读校验（纵深防御，DuckDB read_only 之上再加一层）
"""
from .schema import SCHEMA_INFO

_VALID_TABLE_NAMES = frozenset(SCHEMA_INFO.keys())
_SQL_ALLOWED_PREFIXES = ('SELECT', 'EXPLAIN', 'DESCRIBE', 'SHOW', 'PRAGMA', 'WITH')


def validate_table_name(table_name: str):
    """只允许操作已知的表，拒绝任意表名（防止通过表名注入）"""
    if table_name not in _VALID_TABLE_NAMES:
        raise ValueError(
            f"表 '{table_name}' 不存在。"
            f"可用表：{', '.join(sorted(_VALID_TABLE_NAMES))}"
        )


def validate_readonly_sql(sql: str):
    """只允许只读查询，拒绝 INSERT/UPDATE/DELETE/DROP/ALTER/CREATE 等写操作"""
    stripped = sql.strip()
    # 去除行首注释
    while stripped.startswith('--'):
        rest = stripped.split('\n', 1)
        stripped = rest[1].strip() if len(rest) > 1 else ''
    # 去除块注释
    while stripped.startswith('/*'):
        idx = stripped.find('*/')
        if idx == -1:
            raise ValueError("SQL 格式错误：未闭合的块注释")
        stripped = stripped[idx + 2:].strip()
    if not stripped:
        raise ValueError("SQL 语句为空")
    upper = stripped.upper().lstrip()
    if not any(upper.startswith(p) for p in _SQL_ALLOWED_PREFIXES):
        raise ValueError(
            f"只允许只读操作（SELECT/EXPLAIN/DESCRIBE/SHOW/PRAGMA/WITH），"
            f"不支持: {stripped[:80]}"
        )
