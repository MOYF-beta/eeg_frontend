# 后端 Dockerfile - Django + Channels
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制 requirements.txt
COPY requirements.txt ./

# 安装 Python 依赖（使用国内镜像源加速）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动 Daphne 服务器 (支持 WebSocket)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "eeg_backend.asgi:application"]
