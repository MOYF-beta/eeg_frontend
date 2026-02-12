#!/bin/bash
# Electron打包脚本

set -e

echo "🚀 EEG脑电系统 - Electron打包脚本"
echo "=================================="

# 检查前置条件
echo "📋 检查环境..."
if ! command -v node &> /dev/null; then
    echo "❌ 错误: 需要安装Node.js"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 需要安装Python3"
    exit 1
fi

# 安装依赖
echo "📦 安装前端依赖..."
cd frontend
npm install

echo "📦 安装Electron依赖..."
cd ../electron
npm install

# 构建前端
echo "🏗️  构建前端应用..."
cd ../frontend
npm run build

# 复制构建产物
echo "📁 准备Electron资源..."
cd ../electron
mkdir -p dist
cp -r ../frontend/dist/* dist/

# 打包应用
echo "📦 打包Electron应用..."
npm run electron:build

echo ""
echo "✅ 打包完成!"
echo "📂 输出目录: electron/release/"
echo ""
echo "可执行文件:"
ls -lh release/*/EEG脑电系统* 2>/dev/null || ls -lh release/*/
