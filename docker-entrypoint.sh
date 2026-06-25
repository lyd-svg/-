#!/bin/bash
# ============================================
# Docker 入口点 — 启动所有 MCP 服务器 + UI
# ============================================
set -e

echo "=========================================="
echo "  多智能体数据分析系统 - Docker 启动"
echo "=========================================="
echo ""

# ── 容器停止时清理后台 MCP 进程 ──
cleanup() {
    echo ""
    echo "[停止] 正在停止所有 MCP 服务..."
    python run.py --stop 2>/dev/null || true
    echo "[停止] 服务已停止"
}
trap cleanup EXIT

# ── 加载 .env 配置（通过环境变量传入，或在 .env 文件中配置）──
if [ -f .env ]; then
    echo "[启动] 加载 .env 配置..."
    set -a
    . .env
    set +a
fi

# ── 检查 DeepSeek API Key ──
if [ -z "$DEEPSEEK_API_KEY" ] || [ "$DEEPSEEK_API_KEY" = "your_deepseek_api_key_here" ]; then
    echo "[错误] 未设置 DEEPSEEK_API_KEY"
    echo "  请在 .env 文件中填入您的 DeepSeek API Key"
    echo "  或在 docker run 时传入环境变量: -e DEEPSEEK_API_KEY=sk-xxx"
    echo ""
    echo "  获取地址: https://platform.deepseek.com/api_keys"
    exit 1
fi

# ── 启动 MCP 服务器（后台，通过统一脚本管理）──
echo "[启动] 启动 MCP 服务器..."

python run.py --server &
PID_MCP=$!
echo "  MCP 服务器组 PID=$PID_MCP"

# ── 等待所有 MCP 服务器就绪 ──
echo ""
echo "[启动] 等待 MCP 服务器就绪..."
sleep 3

PORTS=(8000 8001 8002 8003)
NAMES=("DB" "Analysis" "RAG" "Calculator")
for i in "${!PORTS[@]}"; do
    PORT=${PORTS[$i]}
    NAME=${NAMES[$i]}
    for j in $(seq 1 30); do
        if python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('127.0.0.1', $PORT)); s.close()" 2>/dev/null; then
            echo "  ✅ $NAME Server (:${PORT}) 就绪"
            break
        fi
        if [ $j -eq 30 ]; then
            echo "  ⚠️  $NAME Server (:${PORT}) 未在预期时间内就绪，继续启动..."
        fi
        sleep 1
    done
done

echo ""
echo "=========================================="
echo "  所有服务已就绪！"
echo ""
echo "  Streamlit UI:  http://localhost:8501"
echo "=========================================="
echo ""

# ── 启动 Streamlit 前端（前台）──
exec streamlit run app.py --server.port=8501 --server.address=0.0.0.0
