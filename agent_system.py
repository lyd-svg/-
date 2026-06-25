"""
多智能体数据分析系统（兼容入口）
已重构到 agent_system/ 包

保持向后兼容：直接从新包导入所有公共接口
"""
import sys

# 修复 Windows 控制台编码
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except OSError:
    pass

from agent_system.cli import main

if __name__ == "__main__":
    main()
