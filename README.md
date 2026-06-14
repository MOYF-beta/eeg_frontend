# EEG 脑电系统（Windows CMD 安装与启动指南）

本项目是 Vue3 + Vite 前端与 Django + Channels 后端组成的实时脑电系统。

本文档使用 Windows 的 `cmd` 命令行，按顺序执行即可完成安装和启动。

## 0. 准备目录

假设项目目录为：

```cmd
D:\projects\eeg_frontend
```

后续命令请按你的实际路径替换。

## 1. 安装 Node.js（含 npm）

在 `cmd` 中执行：

```cmd
winget install -e --id OpenJS.NodeJS.LTS
```

安装完成后，关闭并重新打开一个 `cmd`，验证：

```cmd
node -v
npm -v
```

## 2. 安装 Conda（Miniconda）

在 `cmd` 中执行：

```cmd
winget install -e --id Anaconda.Miniconda3
```

安装完成后，关闭并重新打开一个 `cmd`，验证：

```cmd
conda --version
```

## 3. 创建并激活 Python Conda 环境

推荐使用 Python 3.10：

```cmd
conda create -n eeg_py310 python=3.10 -y
conda activate eeg_py310
```

## 4. 安装后端依赖

```cmd
cd /d D:\projects\eeg_frontend\backend
pip install -r requirements.txt
```

## 5. 安装前端依赖

```cmd
cd /d D:\projects\eeg_frontend\frontend
npm install
```

## 6. 启动后端服务（cmd 窗口 1）

新开一个 `cmd`，执行：

```cmd
conda activate eeg_py310
cd /d D:\projects\eeg_frontend\backend
python manage.py migrate
daphne -b 0.0.0.0 -p 8000 eeg_backend.asgi:application
```

后端启动后会监听 `8000` 端口。

## 7. 启动前端服务（cmd 窗口 2）

再开一个新的 `cmd`，执行：

```cmd
cd /d D:\projects\eeg_frontend\frontend
npm run dev
```

前端默认监听 `5173` 端口。

## 8. 打开系统

浏览器访问：

```text
http://localhost:5173/
```

## 8.1 实时调试（推荐）

用于复现和验证“真实设备数据链路 + 前端波形显示”。

### A. 启动服务

后端（窗口 1）：

```cmd
conda activate eeg_py310
cd /d D:\projects\eeg_frontend\backend
daphne -b 127.0.0.1 -p 8000 eeg_backend.asgi:application
```

前端（窗口 2）：

```cmd
cd /d D:\projects\eeg_frontend\frontend
npm run dev
```

### B. 执行 20 秒截图调试用例

```cmd
cd /d D:\projects\eeg_frontend\frontend
npm run test:e2e:real-debug
```

输出截图位置：

```text
frontend/e2e/screenshots/debug-real-device-20s.png
```

### C. 可用后端调试接口（串口模拟器）

- `POST /api/real-devices/simulator/start/`：启动模拟器并返回虚拟串口。
- `POST /api/real-devices/simulator/stop/`：停止模拟器。
- `GET /api/real-devices/simulator/status/`：查看模拟器状态。

说明：模拟器按真实设备帧协议输出 8 通道 int32 数据，适合回归测试和前端波形验证。

## 9. 常见问题

### Q1: `conda activate` 提示不是内部或外部命令

先重开 `cmd`；若仍失败，执行一次：

```cmd
conda init cmd.exe
```

然后关闭并重新打开 `cmd`。

### Q2: 前端安装慢或失败

可先清理缓存后重试：

```cmd
npm cache clean --force
npm install
```

### Q3: 端口被占用

查看端口占用：

```cmd
netstat -ano | findstr :5173
netstat -ano | findstr :8000
```

按 PID 结束进程（将 `<PID>` 改为实际数字）：

```cmd
taskkill /PID <PID> /F
```

### Q4: Playwright 用例找不到浏览器

先安装 Playwright 浏览器：

```cmd
cd /d D:\projects\eeg_frontend\frontend
npx playwright install chromium
```

然后重试：

```cmd
npm run test:e2e:real-debug
```