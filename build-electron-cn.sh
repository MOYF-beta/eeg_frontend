#!/bin/bash
# ============================================
# EEG脑电系统 - Electron打包脚本 (国内镜像版)
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 EEG脑电系统 - Electron打包 (国内镜像版)"
echo "======================================="

# 配置国内镜像
echo "📦 配置国内镜像源..."
npm config set electron_mirror https://npmmirror.com/mirrors/electron/
npm config set electron_builder_binaries_mirror https://npmmirror.com/mirrors/electron-builder-binaries/

echo "📋 检查环境..."
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 需要安装Node.js"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要安装Python3"
    exit 1
fi

echo "✅ Node.js: $(node -v)"
echo "✅ Python3: $(python3 --version)"
echo ""

# 构建前端
echo "🏗️  构建前端应用..."
cd frontend
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run build
echo "✅ 前端构建完成"
echo ""

# 准备Electron目录
echo "📁 准备Electron资源..."
cd "$SCRIPT_DIR"
mkdir -p electron/dist
cp -r frontend/dist/* electron/dist/
mkdir -p electron/resources/backend
cp -r backend/* electron/resources/backend/
rm -rf electron/resources/backend/__pycache__
echo "✅ 资源准备完成"
echo ""

# 安装Electron依赖
echo "📦 安装Electron依赖..."
cd electron
if [ ! -d "node_modules" ]; then
    # 使用国内镜像安装
    ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ \
    ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/ \
    npm install
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
    *)          PLATFORM_NAME="linux";;
esac

echo "检测到平台: $PLATFORM_NAME"
echo ""

# 使用国内镜像打包
ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ \
ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/ \
npx electron-builder --${PLATFORM_NAME}

echo ""
echo "================================"

# 检查输出
if [ -d "release" ] && [ "$(ls -A release)" ]; then
    echo "✅ 打包完成!"
    echo ""
    echo "📂 输出目录: electron/release/"
    echo ""
    echo "可执行文件:"
    find release -maxdepth 2 -type f \( -name "*.exe" -o -name "*.AppImage" -o -name "*.dmg" \) -exec ls -lh {} \; 2>/dev/null || ls -lh release/*/
else
    echo "❌ 打包可能失败，请检查错误信息"
fi

echo ""
echo "⚠️  注意: 此版本需要目标机器安装Python3"
echo "    如需独立版本，请运行: ./build-electron-full.sh"
