# ============================================
# 多智能体数据分析系统 - Docker 部署
# ============================================
# 所有 MCP 服务器和 Streamlit 前端在同一个容器内运行。
# docker-entrypoint.sh 负责启动和健康检查。
# ============================================

FROM python:3.11-slim

# ── 环境变量（必须在模型下载前设置）──
ENV TRANSFORMERS_OFFLINE=1
ENV HF_ENDPOINT=https://hf-mirror.com

WORKDIR /app

# ── 系统依赖（sentence-transformers / ChromaDB 需要编译依赖）──
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── 安装 Python 依赖 ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 预先下载 sentence-transformer 模型（构建时缓存，运行时离线使用）──
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

# ── 复制项目代码 ──
COPY . .

# ── 创建运行时需要的目录（这些目录被 .gitignore 排除，构建时不存在）──
RUN mkdir -p vector_db logs reports/charts

# ── 启动脚本权限 ──
RUN chmod +x docker-entrypoint.sh

# ── 暴露端口（仅 Streamlit UI 需要从宿主机访问）──
EXPOSE 8501

ENTRYPOINT ["./docker-entrypoint.sh"]
