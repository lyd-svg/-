"""
MCP Server 统一启动管理器（兼容别名）
统一脚本已迁移到 run.py

用法：
  python run.py              # 启动服务 + Web 界面（推荐）
  python run.py --cli        # 启动服务 + CLI 模式
  python run.py --server     # 仅启动服务（原 start_all_mcp.py 行为）
  python run.py --stop       # 停止所有服务
"""
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent
VENV_PYTHON = str(BASE_DIR / "venv" / "Scripts" / "python.exe")

print("提示: start_all_mcp.py 已迁移到 run.py")
print("      python run.py --server   (仅启动服务, 等同于旧行为)")
print("      python run.py            (启动服务 + Web 界面)")
print()

subprocess.run([VENV_PYTHON, "run.py", "--server"], cwd=BASE_DIR)
