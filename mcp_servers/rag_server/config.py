"""
RAG 知识库服务 — 配置模块
路径、检索参数、Supabase 连接、限流器
"""
import os
import threading
from dotenv import load_dotenv
from mcp_servers.common import setup_logger, RateLimiter

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# ========== 日志系统 ==========

logger = setup_logger("rag_server", console_prefix="[RAG]")

# ========== 限流器 ==========

rate_limiter = RateLimiter(max_concurrent=5, max_per_second=20, max_queue=30)

# ========== 路径配置 ==========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(BASE_DIR)   # mcp_servers/
BASE_DIR = os.path.dirname(BASE_DIR)   # 项目根目录

KNOWLEDGE_BASE_DIR = os.path.join(BASE_DIR, "knowledge_base")
RAW_DIR = os.path.join(KNOWLEDGE_BASE_DIR, "raw")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_db")
DOC_META_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "doc_meta.json")

os.makedirs(RAW_DIR, exist_ok=True)

# ========== 检索参数 ==========

CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
RRF_K = 60
CANDIDATE_K = 50
DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# ========== Supabase 配置 ==========

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

_supabase = None
_supabase_available = True  # 启动后会被 _init_indexes 覆盖
_supabase_lock = threading.Lock()


def get_supabase():
    """延迟初始化 Supabase 客户端"""
    global _supabase, _supabase_available
    if not _supabase_available:
        raise RuntimeError("Supabase 不可用（连接超时或项目已暂停），请检查项目状态")
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError(
                "Supabase 未配置。请设置环境变量 SUPABASE_URL 和 SUPABASE_KEY。\n"
                "1. 注册 https://supabase.com → 创建项目\n"
                "2. 在 Supabase SQL Editor 中运行 supabase_migration.sql\n"
                "3. 将 Project URL 和 anon key 填入 .env 文件"
            )
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


def set_supabase_available(available: bool):
    """设置 Supabase 可用状态"""
    global _supabase_available
    _supabase_available = available


def is_supabase_available() -> bool:
    """检查 Supabase 是否可用"""
    return _supabase_available
