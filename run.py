"""
统一启动脚本
一键启动所有服务：MCP 服务器 + Web/CLI 界面

用法：
  python run.py                  # 启动 MCP 服务 + Streamlit Web
  python run.py --cli            # 启动 MCP 服务 + CLI 交互模式
  python run.py --server         # 仅启动 MCP 服务（后台监控）
  python run.py --stop           # 停止所有服务
"""
import os
import sys
import time
import signal
import subprocess
import argparse
import socket
from pathlib import Path

BASE_DIR = Path(__file__).parent
VENV_PYTHON = str(BASE_DIR / "venv" / "Scripts" / "python.exe")

SERVERS = [
    {"name": "数据库查询服务",  "module": "mcp_servers.db_server.main",         "port": 8000},
    {"name": "可视化分析服务",  "module": "mcp_servers.analysis_server.main",   "port": 8001},
    {"name": "知识库RAG检索服务", "module": "mcp_servers.rag_server.main",      "port": 8002},
    {"name": "计算器服务",      "module": "mcp_servers.calculator_server.main", "port": 8003},
]

_procs: list[subprocess.Popen] = []


# ── 工具函数 ──


def port_open(port: int) -> bool:
    """检查端口是否已开放"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port: int):
    """杀掉占用指定端口的进程"""
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                parts = line.strip().split()
                pid = parts[-1]
                subprocess.run(["taskkill", "-f", "-pid", pid],
                               capture_output=True, timeout=5)
                print(f"  [停止] 端口 {port} 的旧进程 [PID {pid}]")
                return
    except Exception:
        pass


def log(msg: str):
    """带时间戳的日志输出"""
    ts = time.strftime("%H:%M:%S")
    try:
        print(f"  [{ts}] {msg}", flush=True)
    except UnicodeEncodeError:
        safe = msg.encode("ascii", errors="replace").decode("ascii")
        print(f"  [{ts}] {safe}", flush=True)


# ── 服务管理 ──


def stop_servers():
    """停止所有服务"""
    log("正在停止所有服务...")
    for p in _procs:
        if p.poll() is None:
            p.terminate()
    # 等待进程退出
    for p in _procs:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    _procs.clear()
    # 补杀：确保端口全部释放
    for srv in SERVERS:
        if port_open(srv["port"]):
            kill_port(srv["port"])
    log("所有服务已停止")


def start_server(cfg: dict, index: int | None = None) -> subprocess.Popen:
    """启动单个 MCP 服务器，返回进程对象
    如果指定 index，则替换 _procs 中对应位置的进程（重启时使用）
    """
    name = cfg["name"]
    module = cfg["module"]
    port = cfg["port"]

    if port_open(port):
        log(f"({name}) 端口 {port} 被占用，正在清理...")
        kill_port(port)
        time.sleep(1)

    log(f"({name}) 启动中...")

    proc = subprocess.Popen(
        [VENV_PYTHON, "-m", module],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=BASE_DIR,
    )
    if index is not None:
        _procs[index] = proc
    else:
        _procs.append(proc)
    return proc


def wait_for_port(port: int, timeout: float = 30) -> bool:
    """等待端口开放，最多 timeout 秒"""
    for _ in range(int(timeout)):
        if port_open(port):
            return True
        time.sleep(1)
    return False


def start_all_servers() -> bool:
    """启动所有 MCP 服务器，全部就绪返回 True"""
    print()
    print("=" * 56)
    print("  多智能体数据分析系统 - 服务启动")
    print("=" * 56)
    print()

    for srv in SERVERS:
        start_server(srv)

    # 等待所有服务就绪
    all_ok = True
    for srv in SERVERS:
        ok = wait_for_port(srv["port"])
        if ok:
            log(f"[OK] {srv['name']} 就绪 [端口 {srv['port']}]")
        else:
            log(f"[!!] {srv['name']} 启动超时 [端口 {srv['port']}]")
            all_ok = False

    print()
    if all_ok:
        log("所有 MCP 服务已就绪")
    else:
        log("部分服务启动失败，请检查日志")
    print()

    return all_ok


# ── 入口 ──


def main():
    # 修复 Windows 控制台编码
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except OSError:
        pass

    parser = argparse.ArgumentParser(description="多智能体数据分析系统 - 统一启动脚本")
    parser.add_argument("--cli", action="store_true", help="启动 MCP 服务后进入 CLI 模式")
    parser.add_argument("--server", action="store_true", help="仅启动 MCP 服务，不启动界面")
    parser.add_argument("--stop", action="store_true", help="停止所有服务")
    args = parser.parse_args()

    # ── --stop 模式 ──
    if args.stop:
        stop_servers()
        return

    # ── 注册退出清理 ──
    def _cleanup(signum=None, frame=None):
        print()
        stop_servers()
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    # ── 启动 MCP 服务器 ──
    all_ok = start_all_servers()
    if not all_ok and args.server:
        print("  服务未完全就绪，但仍继续运行（按 Ctrl+C 停止）\n")
    elif not all_ok:
        print("  关键服务未就绪，请检查后重试")
        stop_servers()
        sys.exit(1)

    # ── --server 模式：仅启动服务，保持前台监控 ──
    if args.server:
        print("  服务监控中，按 Ctrl+C 停止所有服务...\n")
        try:
            while True:
                time.sleep(1)
                for i, p in enumerate(_procs):
                    if i >= len(SERVERS):
                        continue  # 超出配置的服务列表，跳过
                    if p.poll() is not None:
                        log(f"({SERVERS[i]['name']}) 已退出，正在重启...")
                        start_server(SERVERS[i], index=i)
        except KeyboardInterrupt:
            stop_servers()
        return

    # ── 默认模式：启动服务后打开 Web / CLI ──
    if args.cli:
        log("进入 CLI 交互模式")
        print()
        cli_proc = subprocess.Popen(
            [VENV_PYTHON, "-m", "agent_system.cli"],
            cwd=BASE_DIR,
        )
        try:
            cli_proc.wait()
        except KeyboardInterrupt:
            pass
        finally:
            stop_servers()
    else:
        # Streamlit Web 界面
        log("启动 Streamlit Web 界面")
        log("打开浏览器访问 http://localhost:8501")
        print()
        web_proc = subprocess.Popen(
            [VENV_PYTHON, "-m", "streamlit", "run", "app.py",
             "--server.headless", "true"],
            cwd=BASE_DIR,
        )
        try:
            web_proc.wait()
        except KeyboardInterrupt:
            pass
        finally:
            stop_servers()


if __name__ == "__main__":
    main()
