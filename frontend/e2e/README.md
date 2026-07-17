# EEG系统 Playwright E2E 测试

## 测试结构

```
e2e/
├── helpers.ts                          # 通用辅助函数（WS 命令、API 调用、导航）
├── eeg-system.spec.ts                  # 主测试套件（计算图/示波器/设备/性能）
├── graph-editor.spec.ts                # 计算图基础回归
├── graph-export-import.spec.ts         # 导出/加载 JSON
├── graph-led-workspace.spec.ts         # 设备集合工作台
├── visualization.spec.ts               # ★ 可视化工作台（网格/卡片/持久化）
├── device-management.spec.ts           # ★ 设备管理页面（扫描/CRUD/联调）
├── serial-debug.spec.ts                # ★ 串口调试页面（编码/刷新/数据展示）
├── sidebar-statusbar.spec.ts           # ★ 侧边栏导航 + 状态栏 + 录制
├── control-websocket.spec.ts           # ★ ws/control/ 命令（freeze/run/sync/冲突/心跳/多客户端）
├── virtual-device-full.spec.ts         # ★ 虚拟设备完整数据流（发现/生命周期/数据质量/CORS）
├── virtual-device-e2e.spec.ts          # 虚拟设备基础 E2E
├── node-edit.spec.ts                   # ★ 节点编辑（对话框/只读/同步/清空）
├── fullscreen-devhub.spec.ts           # ★ 全屏视图 + 开发目录导航
├── api-endpoints.spec.ts               # ★ 后端 HTTP API 端点全覆盖
├── real-device-debug.spec.ts           # 真实设备链路调试
├── sidebar-collapsed-controls.spec.ts  # 侧边栏折叠态
├── screenshots/                        # 测试截图
└── README.md                           # 本文档
```

（★ 为新增测试文件）

## 测试覆盖

### 1. 计算图编辑器
- ✅ 页面基本结构与节点库分组
- ✅ 加载计算图
- ✅ 冻结开关功能
- ✅ 保存计算图（持久化验证）
- ✅ 双击编辑节点
- ✅ 导出/加载 JSON（含错误处理）
- ✅ 清空画布
- ✅ 节点编辑对话框字段验证
- ✅ 冻结态只读模式

### 2. 可视化工作台
- ✅ 页面加载与标题
- ✅ 网格布局切换（1x1/2x2/3x3/4x4）
- ✅ 添加示波器/频谱/10-20 可视化卡片
- ✅ 布局 localStorage 持久化与刷新恢复
- ✅ 数据流绑定（前后端联调）

### 3. 示波器
- ✅ 基本结构验证
- ✅ 绑定/解除绑定 OUTPUT 节点
- ✅ 性能测试（内存不无限增长）

### 4. 设备管理
- ✅ 设备列表基本结构
- ✅ 真实设备管理（一键扫描）
- ✅ 添加/编辑设备对话框
- ✅ 设备 CRUD API 联调
- ✅ 绑定设备到 SOURCE 节点

### 5. 串口调试
- ✅ 页面加载与控件（端口/编码/样本数/自动刷新）
- ✅ 刷新按钮
- ✅ 文本编码切换
- ✅ 模拟器数据展示联调

### 6. 侧边栏与状态栏
- ✅ 导航跳转（计算图/可视化/开发目录）
- ✅ 运行/停止按钮（data-testid）
- ✅ 录制按钮
- ✅ 状态栏性能指标（CPU/RAM/WS 状态）

### 7. WebSocket 控制通道（ws/control/）
- ✅ 连接与初始 state 推送
- ✅ freeze/run/stop 命令
- ✅ sync_graph 图同步 + 冲突检测
- ✅ save_graph 持久化
- ✅ scan_ports 设备扫描
- ✅ get_state 状态查询
- ✅ ping/pong 心跳
- ✅ 多客户端状态同步

### 8. 虚拟设备完整数据流
- ✅ 虚拟设备服务器健康检查
- ✅ 5 个 sim_* 设备发现
- ✅ 设备生命周期（连接→采集→数据→停止→断开）
- ✅ 数据质量（通道数一致性）
- ✅ CORS 跨域
- ✅ 完整数据流：冻结→运行→示波器接收

### 9. 全屏视图与开发目录
- ✅ 全屏示波器/频谱路由
- ✅ is-fullscreen-view body class
- ✅ 开发目录导航链接

### 10. 后端 HTTP API 端点
- ✅ /api/health/ /api/status/
- ✅ /api/graph/ GET（POST 返回 405）
- ✅ /api/graph/python/prototype/ /library/
- ✅ /api/saved-files/ /api/replayable-files/
- ✅ /api/real-devices/ CRUD + scan-ports + status
- ✅ /api/graph/record/
- ✅ /api/graph/debug/

### 11. 端到端流程
- ✅ 完整数据流：冻结 → 绑定 → 显示波形
- ✅ 解冻后停止数据流
- ✅ 页面加载性能
- ✅ 长时间运行稳定性

## 运行测试

### 前提条件
确保所有服务运行中：
```bash
# 1. Django 后端（端口 8000）
cd backend && python manage.py runserver 0.0.0.0:8000

# 2. 虚拟设备服务器（端口 7777，用于虚拟设备测试）
cd backend && python eeg_app/virtual_device_server.py

# 3. 前端 dev server（端口 5173）
cd frontend && npm run dev
```

### 运行所有 Playwright 测试
```bash
cd frontend && npx playwright test
```

### 运行特定测试文件
```bash
npx playwright test e2e/visualization.spec.ts
npx playwright test e2e/control-websocket.spec.ts
```

### 运行特定测试用例
```bash
npx playwright test -g "冻结开关功能"
```

### 带UI模式运行（调试）
```bash
npx playwright test --ui
```

### 生成HTML报告
```bash
npx playwright test --reporter=html
```

### 后端测试（pytest）
```bash
cd backend && python -m pytest eeg_app/tests/ -v
```

## 测试截图

测试运行后，截图保存在 `e2e/screenshots/` 目录。

## 辅助函数（helpers.ts）

通用辅助函数位于 `e2e/helpers.ts`，提供：
- `sendControlCmd(page, command, payload)` — 通过 ws/control/ 发送命令
- `prepareGraphViaBrowser(page, graph)` — 准备运行中的图（sync→freeze→run）
- `teardownGraph(page)` — 清理后端运行状态
- `buildMinimalGraph(deviceId?)` — 构造最小测试图（SOURCE→OUTPUT）
- `findVirtualDeviceId(api)` — 获取虚拟设备 ID
- `getPacketCount(page)` — 获取示波器数据包计数
- `clickSidebarNav(page, title)` — 侧边栏导航

## 故障排除

### 测试失败：元素不可见
- 增加 `waitForTimeout` 时间
- 检查后端服务是否运行

### 测试失败：WebSocket未连接
- 确保计算图已冻结
- 检查 `ws://localhost:8000/ws/eeg/` 是否可访问

### 虚拟设备测试被 skip
- 确保虚拟设备服务器运行中（端口 7777）
- 测试会自动检测 `sim_*` 设备并 skip 如果未运行

### 截图为空
- 确保页面完全加载
- 检查是否有JavaScript错误

## 更新测试

当功能变更时，更新对应测试：
1. 修改对应的 `e2e/*.spec.ts` 文件
2. 通用逻辑提取到 `e2e/helpers.ts`
3. 运行测试验证：`npx playwright test`
3. 提交更新
