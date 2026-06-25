"""
统一的日志配置工具
消除 5 个 MCP 服务器中重复的日志初始化代码

用法：
    from mcp_servers.common import setup_logger
    logger = setup_logger("rag_server", console_prefix="[RAG]")
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler


def setup_logger(
    name: str,
    log_dir: str | None = None,
    console_prefix: str = "",
    file_level: int = logging.DEBUG,
    console_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """创建统一配置的日志器

    参数：
        name: 日志器名称（同时也是日志文件名）
        log_dir: 日志目录，默认项目根下的 logs/
        console_prefix: 控制台日志前缀，如 "[RAG]"
        file_level: 文件日志级别
        console_level: 控制台日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件数
    """
    if log_dir is None:
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 避免重复添加 handler（模块重载时）
    if logger.handlers:
        return logger

    # 文件日志（按大小轮转）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"{name}.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # 控制台日志
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    fmt = f"{console_prefix} %(levelname)s %(message)s" if console_prefix else "%(levelname)s %(message)s"
    console_handler.setFormatter(logging.Formatter(fmt))

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
