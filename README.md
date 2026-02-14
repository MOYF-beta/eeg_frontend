# EEG 脑电系统

Vue3 + Vite + Django + WebSocket 实时脑电数据可视化系统

## 功能特性

- **计算图编辑器**: 可视化拖拽构建数据处理流程
- **扫描模式示波器**: 类似医院监护仪的扫描线显示，从左到右移动，左侧新数据右侧旧数据
- **设备管理**: 设备增删改查，绑定状态显示
- **实时数据流**: WebSocket 传输，30fps 刷新率

## 技术栈

### 前端
- Vue 3 + Composition API
- Vite 5.x
- Vuetify 3
- @antv/x6 (计算图可视化)
- ECharts (波形显示)

### 后端
- Django
- Django Channels (WebSocket)
- Daphne (ASGI 服务器)

## 项目结构

```
eeg_frontend/
├── frontend/          # Vue3 前端
│   ├── src/
│   │   ├── components/    # 组件
│   │   │   ├── GraphEditor.vue      # 计算图编辑器
│   │   │   ├── Oscilloscope.vue     # 扫描模式示波器
│   │   │   ├── DeviceList.vue       # 设备管理
│   │   │   └── nodes/
│   │   │       └── NodeEditDialog.vue   # 节点编辑（含设备绑定）
│   │   ├── services/
│   │   │   ├── graph.ts       # API 接口
│   │   │   ├── sessionStore.ts    # 状态管理
│   │   │   └── websocket.ts   # WebSocket 连接
│   │   └── views/
│   └── package.json
├── backend/           # Django 后端
│   ├── eeg_app/
│   │   ├── consumers.py       # WebSocket Consumer
│   │   ├── graph_consumer.py  # 计算图数据流
│   │   ├── graph_store.py     # 计算图存储
│   │   └── views.py           # API 视图
│   └── manage.py
```

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

- 计算图: http://localhost:5173/cpgraph
- 设备管理: http://localhost:5173/devices
- 可视化: http://localhost:5173/visualization
- 后端 API: http://localhost:8000/api/

## 核心功能说明

### 扫描模式示波器

不同于传统的滚动模式，扫描模式下：
- 扫描线从左到右移动
- 线的左侧显示新数据
- 线的右侧显示旧数据
- 到达最右端后回到最左端重新开始
- 图形稳定不滚动，只有扫描线移动

### 设备绑定流程

1. 在 `/devices` 页面添加设备
2. 在 `/cpgraph` 计算图编辑器添加 SOURCE 节点
3. 双击 SOURCE 节点编辑，选择绑定的设备
4. 冻结计算图并运行

### 运行按钮状态

- 未运行: 绿色「运行」按钮
- 运行中: 红色「停止」按钮 + 「运行中」标签
- 每 2 秒轮询后端状态

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| /api/graph/ | GET/POST | 获取/保存计算图 |
| /api/graph/freeze/ | POST | 冻结/解冻计算图 |
| /api/graph/run/ | GET/POST/DELETE | 获取状态/启动/停止运行 |
| /api/devices/ | GET | 获取设备列表 |
| ws://localhost:8000/ws/eeg/ | WebSocket | 实时数据流 |

## 注意事项

- 冻结前需确保所有 SOURCE 节点已绑定设备
- WebSocket 依赖 Django Channels，必须使用 Daphne 运行
- 开发模式下前端会自动代理 API 请求到后端

## 最近更新

- v5: 扫描模式示波器、设备绑定移至节点编辑、运行按钮状态显示
