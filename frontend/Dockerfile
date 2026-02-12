# 前端 Dockerfile - Vue 3 + Vite (生产模式)
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm config set registry https://registry.npmmirror.com && npm install --legacy-peer-deps
COPY . .
RUN npm run build

# 使用 nginx 托管静态文件
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
