#!/bin/bash
# ============================================
# EEG脑电系统 - Electron打包脚本 (完整版)
# ============================================
# 特点:
# - 体积较大 (~150MB)
# - 无需Python环境，开箱即用
# - 适合普通用户或离线环境
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 EEG脑电系统 - Electron打包 (完整版)"
echo "======================================="
echo "特点: 独立运行, 无需Python环境"
echo ""

# 检查环境
echo "📋 检查环境..."
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 需要安装Node.js (v18+)"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要安装Python3用于打包"
    exit 1
fi

# 检查pyinstaller
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "📦 安装PyInstaller..."
    pip3 install pyinstaller
fi

echo "✅ 环境检查通过"
echo ""

# ============================================
# 第一步: 用PyInstaller打包Django后端
# ============================================
echo "🏗️  步骤1: 打包Django后端..."
echo "================================"
cd backend

# 创建PyInstaller spec文件
cat > eeg_backend.spec << 'SPECEOF'
# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

a = Analysis(
    ['manage.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('eeg_app', 'eeg_app'),
        ('eeg_backend', 'eeg_backend'),
    ],
    hiddenimports=[
        'django',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'channels',
        'channels.routing',
        'daphne',
        'rest_framework',
        'corsheaders',
        'eeg_app',
        'eeg_app.graph_consumer',
        'eeg_app.graph_store',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='eeg_backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
SPECEOF

# 执行PyInstaller打包
echo "   正在打包，这可能需要几分钟..."
pyinstaller eeg_backend.spec --clean --noconfirm 2>&1 | grep -E "(INFO|ERROR|Building|Completed)" || true

if [ ! -f "dist/eeg_backend" ] && [ ! -f "dist/eeg_backend.exe" ]; then
    echo "❌ 后端打包失败"
    exit 1
fi

echo "✅ Django后端打包完成"
echo ""

# ============================================
# 第二步: 构建前端
# ============================================
echo "🏗️  步骤2: 构建前端..."
echo "================================"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    npm install
fi

npm run build
echo "✅ 前端构建完成"
echo ""

# ============================================
# 第三步: 准备Electron资源
# ============================================
echo "📁 步骤3: 准备Electron资源..."
echo "================================"
cd "$SCRIPT_DIR"

mkdir -p electron/dist
cp -r frontend/dist/* electron/dist/

# 复制打包后的后端
mkdir -p electron/resources/backend-dist
cp backend/dist/eeg_backend* electron/resources/backend-dist/ 2>/dev/null || cp backend/dist/eeg_backend electron/resources/backend-dist/
echo "✅ 资源准备完成"
echo ""

# ============================================
# 第四步: 修改Electron配置使用打包版后端
# ============================================
echo "🔧 步骤4: 配置Electron使用打包版后端..."
echo "================================"

# 创建完整版主进程文件
cat > electron/main-full.js << 'MAINEOF'
const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn, execFile } = require('child_process');

let mainWindow;
let backendProcess;
const BACKEND_PORT = 8000;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'EEG脑电系统',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    show: false,
    backgroundColor: '#f5f5f5'
  });

  const isDev = process.env.NODE_ENV === 'development';
  
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist/index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    startBackend();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
    stopBackend();
  });
}

function startBackend() {
  console.log('[Electron] Starting packaged backend...');
  
  const isPackaged = app.isPackaged;
  let backendExecutable;
  
  if (isPackaged) {
    // 打包后的路径
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';
    backendExecutable = path.join(process.resourcesPath, 'backend-dist', `eeg_backend${ext}`);
  } else {
    // 开发环境
    const platform = process.platform;
    const ext = platform === 'win32' ? '.exe' : '';
    backendExecutable = path.join(__dirname, 'resources/backend-dist', `eeg_backend${ext}`);
  }
  
  console.log(`[Electron] Backend executable: ${backendExecutable}`);
  
  // 使用execFile启动打包后的后端
  backendProcess = execFile(backendExecutable, ['runserver', `0.0.0.0:${BACKEND_PORT}`], {
    env: {
      ...process.env,
      DJANGO_SETTINGS_MODULE: 'eeg_backend.settings'
    }
  }, (error, stdout, stderr) => {
    if (error) {
      console.error('[Backend Error]', error);
    }
  });
  
  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });
  
  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error] ${data.toString().trim()}`);
  });
  
  setTimeout(() => {
    if (mainWindow) {
      mainWindow.webContents.send('backend-ready', `http://localhost:${BACKEND_PORT}`);
    }
  }, 3000);
}

function stopBackend() {
  if (backendProcess) {
    console.log('[Electron] Stopping backend...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    backendProcess = null;
  }
}

ipcMain.handle('get-backend-url', () => `http://localhost:${BACKEND_PORT}`);

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', stopBackend);
MAINEOF

echo "✅ Electron配置完成"
echo ""

# ============================================
# 第五步: 打包Electron应用
# ============================================
echo "📦 步骤5: 打包Electron应用..."
echo "================================"
cd electron

if [ ! -d "node_modules" ]; then
    npm install
fi

# 临时替换main.js为完整版
cp main.js main-simple.js
cp main-full.js main.js

# 检测平台
PLATFORM=$(uname -s)
case "$PLATFORM" in
    Linux*)     PLATFORM_NAME="linux";;
    Darwin*)    PLATFORM_NAME="mac";;
    CYGWIN*|MINGW*|MSYS*) PLATFORM_NAME="win";;
    *)          PLATFORM_NAME="linux";;
esac

echo "检测到平台: $PLATFORM_NAME"

if [ "$PLATFORM_NAME" = "win" ]; then
    npm run electron:build:win
elif [ "$PLATFORM_NAME" = "mac" ]; then
    npm run electron:build:mac
else
    npm run electron:build:linux
fi

# 恢复原来的main.js
mv main-simple.js main.js
rm -f main-full.js

echo ""
echo "================================"
echo "✅ 完整版打包完成!"
echo ""
echo "📂 输出目录: electron/release/"
echo ""
echo "可执行文件:"
find electron/release -maxdepth 2 -type f \( -name "*.exe" -o -name "*.AppImage" -o -name "*.dmg" \) -exec ls -lh {} \; 2>/dev/null

echo ""
echo "✨ 特点: 独立运行，无需Python环境"
echo "📦 体积: 约100-150MB (包含完整Python运行时)"
echo ""
