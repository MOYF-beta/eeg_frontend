## 前提条件：启动所有服务

```bash
# 1. Django 后端（端口 8000）
cd backend && /home/zch/Documents/eeg_frontend/.venv/bin/python manage.py runserver 0.0.0.0:8000

# 2. 虚拟设备服务器（端口 7777，用于虚拟设备 / 完整 E2E 测试）
cd backend && /home/zch/Documents/eeg_frontend/.venv/bin/python eeg_app/virtual_device_server.py

# 3. 前端 dev server（端口 5173）
cd frontend && npm run dev
```

## 后端测试（pytest，110 个）

```bash
cd backend && /home/zch/Documents/eeg_frontend/.venv/bin/python -m pytest eeg_app/tests/ -v
```

测试文件：
- `test_virtual_device_server.py` — 虚拟设备服务器 API
- `test_simulator_driver.py` — 模拟设备驱动
- `test_device_graph_integration.py` — 设备 + 图集成
- `test_http_views.py` — HTTP 视图层（23 个）
- `test_websocket_consumers.py` — WS Consumer 命令（13 个）
- `test_end_to_end_flow.py` — 端到端数据流（4 个）

## 前端单元测试（vitest，12 个）

```bash
cd frontend && npx vitest run
```

## 前端 E2E 测试（Playwright，需要所有服务运行中）

### 完整测试套件（有序执行，复用活跃前后端状态）

```bash
cd frontend && npm run test:e2e:full
```

执行顺序（playwright.config.ts 中 4 个有序 project）：
1. **robustness** — 32 个鲁棒性 / 边界测试
2. **combo-regression** — 24 个组合回归（边界条件 → E2E 恢复验证）
3. **user-journey** — 10 个模拟用户完整旅程
4. **other-e2e** — 其余 E2E 测试

### 单独运行某个阶段

```bash
cd frontend && npm run test:e2e:robustness   # 仅鲁棒性测试（32 个）
cd frontend && npm run test:e2e:combo        # 仅组合回归（24 个）
cd frontend && npm run test:e2e:journey      # 仅用户旅程（10 个）
```

### 运行特定测试文件

```bash
cd frontend && npx playwright test e2e/user-journey.spec.ts
cd frontend && npx playwright test e2e/robustness.spec.ts
cd frontend && npx playwright test e2e/combo-regression.spec.ts
cd frontend && npx playwright test e2e/control-websocket.spec.ts
cd frontend && npx playwright test e2e/virtual-device-full.spec.ts
```

### 运行特定测试用例

```bash
cd frontend && npx playwright test -g "冻结开关功能"
```

### 带UI模式调试

```bash
cd frontend && npx playwright test --ui
```

## 测试覆盖概览

### 后端（110 个 pytest）
- HTTP API 端点全覆盖（health/status/graph/devices/real-devices/record/python）
- WebSocket 命令全覆盖（freeze/run/stop/sync_graph/save_graph/scan_ports/冲突检测/心跳）
- 端到端数据流（sync→freeze→run→数据推送→stop→多客户端同步）
- 设备驱动 + 虚拟设备服务器

### 前端 E2E
| 测试文件 | 内容 |
|---|---|
| `robustness.spec.ts` | 运行时守卫 / 冲突检测 / 无效输入 / offline 校验 / 设备错误 / 录制幂等 / 刷新恢复 / 数据流守卫 / UI 守卫 / 边界图结构 |
| `combo-regression.spec.ts` | 每个边界条件后立即 E2E 验证系统恢复（10 组合） |
| `user-journey.spec.ts` | 设备管理 → 计算图编辑 → 示波器 → 录制（含 CSV 产物验证） |
| `control-websocket.spec.ts` | ws/control/ 命令 + 多客户端同步 |
| `virtual-device-full.spec.ts` | 虚拟设备发现 / 生命周期 / 数据质量 / CORS |
| `visualization.spec.ts` | 网格布局 / 卡片添加 / localStorage 持久化 |
| `node-edit.spec.ts` | 节点编辑对话框 / 只读模式 / 图同步 |
| `device-management.spec.ts` | 设备扫描 / CRUD / 运行时限制 |
| `api-endpoints.spec.ts` | 后端 HTTP API 端点全覆盖 |
| `serial-debug.spec.ts` | 串口调试页面（编码 / 刷新 / 数据展示） |
| `sidebar-statusbar.spec.ts` | 侧边栏导航 / 状态栏 / 录制按钮 |
| `fullscreen-devhub.spec.ts` | 全屏视图 / 开发目录导航 |