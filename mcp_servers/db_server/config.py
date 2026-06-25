"""
数据库连接配置
管理 DuckDB 数据库文件发现和全局连接
"""
import os
import duckdb
from mcp_servers.common import setup_logger, RateLimiter

logger = setup_logger("db_server", console_prefix="[DB]")

# 限流器
rate_limiter = RateLimiter(max_concurrent=10, max_per_second=50, max_queue=50)

# 尝试可用的数据库文件
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.dirname(_BASE_DIR)  # mcp_servers/
_BASE_DIR = os.path.dirname(_BASE_DIR)  # 项目根目录

_DB_CANDIDATES = [
    os.path.join(_BASE_DIR, "ecommerce1.db"),
    os.path.join(_BASE_DIR, "ecommerce.db"),
]
DB_PATH = None
for p in _DB_CANDIDATES:
    if os.path.exists(p):
        DB_PATH = p
        break

# 全局复用连接（DuckDB read_only 线程安全，不必每次新建）
_db_conn = None


def get_connection():
    """获取全局复用的 DuckDB 只读连接"""
    global _db_conn
    if _db_conn is None and DB_PATH:
        try:
            _db_conn = duckdb.connect(DB_PATH, read_only=True)
        except Exception:
            logger.exception("DuckDB 连接失败")
    return _db_conn


def is_db_path_available():
    """数据库文件是否存在且可访问"""
    return DB_PATH is not None and os.path.exists(DB_PATH)
