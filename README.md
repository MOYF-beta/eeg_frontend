# EEG 脑电系统

Vue3 + Vite + Django + WebSocket 实时脑电数据可视化系统


## 快速开始

### 1. 安装依赖

**前端:**
```bash
cd frontend
npm install
```

**后端:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 启动服务

**后端 (端口 8000):**
```bash
cd backend
source venv/bin/activate
daphne -b 0.0.0.0 -p 8000 eeg_backend.asgi:application
```

**前端 (端口 5173):**
```bash
cd frontend
npm run dev
```

### 3. 访问

http://localhost:5173/