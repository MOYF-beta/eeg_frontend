# EEG脑电系统 - Electron桌面应用打包

## 📦 打包方案

使用 **Electron + 嵌入式Python** 方案：
- Electron提供桌面窗口和前端渲染
- Django后端作为子进程启动
- 打包成独立可执行文件（.exe/.dmg/.AppImage）

## 📁 文件结构

```
eeg_frontend/
├── frontend/          # Vue前端（已存在）
│   ├── dist/         # 构建输出
│   └── ...
├── backend/          # Django后端（已存在）
│   └── ...
├── electron/         # Electron配置
│   ├── main.js       # 主进程
│   ├── preload.js    # 预加载脚本
│   └── package.json  # Electron依赖
└── build-electron.sh # 打包脚本
```

## 🚀 快速打包

### 方式1: 自动脚本（推荐）

```bash
# 在项目根目录运行
chmod +x build-electron.sh
./build-electron.sh
```

### 方式2: 手动步骤

```bash
# 1. 进入electron目录
cd electron

# 2. 安装依赖
npm install

# 3. 构建前端
cd ../frontend
npm run build

# 4. 复制前端构建产物到electron
cp -r dist/* ../electron/dist/

# 5. 打包应用
cd ../electron
npm run electron:build
```

## 📦 输出文件

打包完成后，在 `electron/release/` 目录下：

| 平台 | 文件 |
|------|------|
| Windows | `EEG脑电系统 Setup 1.0.0.exe` |
| macOS | `EEG脑电系统-1.0.0.dmg` |
| Linux | `EEG脑电系统-1.0.0.AppImage` |

## 🔧 配置说明

### Electron主进程 (electron/main.js)

- **窗口管理**: 创建1400x900主窗口
- **后端启动**: 自动启动Django服务（端口8000）
- **前端加载**: 加载本地dist/index.html
- **进程管理**: 关闭窗口时自动停止后端

### 后端服务管理

```javascript
// Electron启动时自动启动Django
backendProcess = spawn('python3', [
  'manage.py', 
  'runserver', 
  '0.0.0.0:8000'
]);
```

### IPC通信

渲染进程可通过 `window.electronAPI` 访问：
- `getBackendUrl()` - 获取后端地址
- `restartBackend()` - 重启后端服务
- `onBackendReady(callback)` - 监听后端就绪

## ⚠️ 注意事项

### Python环境
- 目标机器需要安装Python3
- 或使用PyInstaller将Django打包成独立可执行文件

### 端口占用
- 默认使用8000端口
- 如被占用，修改 `BACKEND_PORT` 常量

### 开发调试

```bash
# 开发模式（热重载）
cd electron
npm run electron:dev
```

## 🎯 优化建议

### 方案A: 简单版（当前）
- 要求目标机器安装Python
- 体积小（~50MB）
- 适合技术用户

### 方案B: 完整版（推荐）
使用PyInstaller将Django打包：
```bash
# 后端打包
cd backend
pyinstaller --onefile manage.py --name eeg_backend

# 修改electron/main.js
pythonPath = path.join(__dirname, 'backend/eeg_backend');
```
- 无需Python环境
- 体积大（~150MB）
- 开箱即用

## 📚 参考

- [Electron文档](https://www.electronjs.org/docs)
- [electron-builder](https://www.electron.build/)
- [Django部署](https://docs.djangoproject.com/en/4.2/howto/deployment/)
