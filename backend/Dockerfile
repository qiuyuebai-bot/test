# syntax=docker/dockerfile:1
# ===========================================
# 领域知识个性化生成与多智能体协同决策系统 - 后端
# 多阶段构建 Dockerfile
# 启用 BuildKit 高级特性：--mount=type=cache 加速 pip 与 apt
# ===========================================

# ---- 构建阶段 ----
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 安装构建依赖（仅编译阶段需要）
# 使用 BuildKit cache mount 加速 apt 重复构建
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc

# 复制依赖文件并安装到虚拟环境
# 使用 BuildKit cache mount 加速 pip 重复构建（pip 缓存跨构建复用）
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r requirements.txt

# ---- 运行阶段 ----
FROM python:3.11-slim AS runtime

LABEL maintainer="knowledge-system"
LABEL description="领域知识个性化生成与多智能体协同决策系统 - 后端API"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive \
    APP_ENV=production

WORKDIR /app

# 从构建阶段复制虚拟环境（运行阶段无需额外系统包，Python 自带 urllib 用于健康检查）
COPY --from=builder /opt/venv /opt/venv

# 复制应用代码
COPY . .

# 创建必要目录（数据、日志、上传、向量库）
RUN mkdir -p /app/data /app/logs /app/data/uploads /app/data/chroma_db /app/data/knowledge_docs /app/data/resources

# 暴露端口
EXPOSE 8000

# 健康检查：使用 Python urllib 替代 curl，避免额外系统依赖
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import sys,urllib.request; r=urllib.request.urlopen('http://localhost:8000/health',timeout=5); sys.exit(0 if r.status==200 else 1)"

# 启动命令（单进程，workers 根据需要通过环境变量调整）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
