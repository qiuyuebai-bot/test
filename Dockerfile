# ===========================================
# 领域知识个性化生成与多智能体协同决策系统 - 前端
# 多阶段构建 Dockerfile (Node构建 + Nginx托管)
# ===========================================

# ---- 构建阶段 ----
FROM node:20-alpine AS builder

WORKDIR /app

# 复制 package 文件（利用 Docker 缓存层）
COPY package.json package-lock.json* ./

# 安装依赖（使用 npm ci 保证确定性；无 lockfile 时回退到 npm install）
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

# 复制源代码
COPY . .

# 构建生产版本
RUN npm run build

# ---- 运行阶段 ----
FROM nginx:1.25-alpine AS runtime

LABEL maintainer="knowledge-system"
LABEL description="领域知识个性化生成与多智能体协同决策系统 - 前端"

# 复制自定义 Nginx 配置
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 暴露端口
EXPOSE 80

# 健康检查：Nginx 自带 curl/wget 在 alpine 中用 wget
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
