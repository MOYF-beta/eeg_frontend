#!/bin/bash
# ============================================
# EEG脑电系统 - Electron打包脚本 (简单版)
# ============================================
# 特点:
# - 体积小 (~50MB)
# - 要求目标机器安装Python3
# - 适合技术用户或服务器环境
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 EEG脑电系统 - Electron打包 (简单版)"
echo "======================================="
echo "特点: 体积小(~50MB), 需要Python3环境"
echo ""

# 检查环境
echo "📋 检查环境..."
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 需要安装Node.js (v18+)"
    echo "   请访问: https://nodejs.org/"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要安装Python3"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip"
    echo "   macOS: brew install python3"
    echo "   Windows: 从官网下载安装"
    exit 1
fi

NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "⚠️  警告: Node.js版本过低，建议v18+"
fi

echo "✅ Node.js: $(node -v)"
echo "✅ Python3: $(python3 --version)"
echo ""

# 安装前端依赖
echo "📦 安装前端依赖..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "   (已存在，跳过)"
fi

# 构建前端
echo "🏗️  构建前端应用..."
npm run build
echo "✅ 前端构建完成"
echo ""

# 准备Electron目录
echo "📁 准备Electron资源..."
cd "$SCRIPT_DIR"
mkdir -p electron/dist
cp -r frontend/dist/* electron/dist/

# 复制后端到Electron资源目录
echo "📁 复制后端资源..."
mkdir -p electron/resources/backend
cp -r backend/* electron/resources/backend/
rm -rf electron/resources/backend/__pycache__
rm -rf electron/resources/backend/*.pyc
echo "✅ 资源准备完成"
echo ""

# 安装Electron依赖
echo "📦 安装Electron依赖..."
cd electron
if [ ! -d "node_modules" ]; then
    npm install
else
    echo "   (已存在，跳过)"
fi

# 打包应用
echo ""
echo "📦 开始打包Electron应用..."
echo "================================"

# 检测平台
PLATFORM=$(uname -s)
case "$PLATFORM" in
    Linux*)     PLATFORM_NAME="linux";;
    Darwin*)    PLATFORM_NAME="mac";;
    CYGWIN*|MINGW*|MSYS*) PLATFORM_NAME="win";;
    *)          PLATFORM_NAME="unknown";;
esac

echo "检测到平台: $PLATFORM_NAME"
echo ""

# 执行打包
if [ "$PLATFORM_NAME" = "win" ]; then
    npm run electron:build:win
elif [ "$PLATFORM_NAME" = "mac" ]; then
    npm run electron:build:mac
else
    npm run electron:build:linux
fi

echo ""
echo "================================"
echo "✅ 打包完成!"
echo ""
echo "📂 输出目录: electron/release/"
echo ""
echo "可执行文件:"
find electron/release -maxdepth 2 -type f \( -name "*.exe" -o -name "*.AppImage" -o -name "*.dmg" -o -name "EEG*" \) -exec ls -lh {} \; 2>/dev/null || echo "   (请查看 electron/release/ 目录)"
echo ""
echo "⚠️  注意: 此版本需要目标机器安装Python3"
echo "    如需独立版本(无需Python)，请运行: ./build-electron-full.sh"
echo ""
