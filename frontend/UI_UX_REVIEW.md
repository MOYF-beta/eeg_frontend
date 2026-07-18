# Phase 3.5 界面与体验审查报告

> 日期：2026-07-18 · 范围：前端全部路由（/cpgraph、/visualization、/devices、/dev、/dev/serial-debug）+ 全局组件（Sidebar、StatusBar、App、theme）
> 方法：代码通读 + Playwright 截图 + 关键交互回归 + e2e 基线对比

---

## 一、整体视觉一致性

| 维度 | 现状 | 评价 |
|---|---|---|
| 主题 | Vuetify 3 明暗双主题，CSS 变量驱动；X6 画布网格点色随主题切换（`gridDotColor()`） | 良好 |
| 组件库 | 全局统一 Vuetify 3；X6 仅用于计算图画布；ECharts 仅用于示波器/频谱/10-20 | 良好 |
| 布局 | 左侧 rail 导航 + 顶部/内容区 + 底部 StatusBar 的三段式结构在所有路由一致 | 良好 |
| 图标 | mdi 图标体系统一 | 良好 |
| 命名 | 节点类型、设备状态、运行模式术语在 GraphEditor / Oscilloscope / Devices 之间一致 | 良好 |

**整体结论**：视觉一致性良好，无跨页面风格漂移。

---

## 二、各页面审查

### 2.1 /cpgraph 计算图编辑器（本次重构主战场）

**重构前问题**（已在本次会话全部定位）：
- 单文件 ~3000 行，承担工具栏、节点库、画布、设备管理、双图同步、边动画、通道推断等 10+ 职责
- 死代码：`editDialog` 节点编辑弹窗、`pinnedNodePanel` 示波器弹窗、`createNodeHtml()`、`onDragStart/onDragStartDevice` 与 GraphPalette 重复
- **隐患 bug**：`applyFrozen()` 调用未定义的 `connectWebSocket()` / `disconnectWebSocket()`（冻结切换必抛 ReferenceError）
- 工具栏缺冻结开关与保存按钮（与 e2e 期望不符）
- Sidebar 无 /devices 导航入口

**已落地修复**：
- 新建 `GraphToolbar.vue`（冻结开关 + 同步状态 chip + 保存/导出/加载/清空 + 端口图例 + 设备管理入口）
- 新建 `GraphPalette.vue`（搜索框 + 设备/回放/处理/输出四个折叠面板，自含拖拽守卫）
- GraphEditor 删除死代码约 400 行，修复 `applyFrozen` ReferenceError
- 修复 server push `reason === 'freeze'` 未处理的告警
- Sidebar 新增「设备管理」导航；App.vue 删除 `height:100% !important` 覆盖

**验证**：
- vue-tsc：新增两组件 0 错误
- 浏览器：工具栏/节点库/节点编辑侧边栏全部正常，冻结切换无 ReferenceError
- e2e 基线对比：重构前后均 8 failed / 5 passed，失败集完全相同 → **本次重构零回归**（失败为既有问题，见 §四）

**残留（本次未改）**：
- GraphEditor 仍有 ~2600 行，边动画/通道推断/端口同步等逻辑可进一步抽取
- `onDragOver/onDrop` 定义在 `onMounted` 内但 `onUnmounted` 引用，TS 报 Cannot find name（运行时无碍，属既有类型缺陷）
- 大量 X6 回调隐式 any（既有）

### 2.2 /visualization 波形可视化

- 「计算图未冻结」提示已改为「冻结后即可启动数据流」+ 「立即冻结」主按钮（本次已落地）
- 布局网格 1X1–4X4、添加示波器/频谱/10-20 按钮齐全
- 8 通道增益控制渲染正常
- **既有 UX 问题**：SOURCE 节点通道数=4 时，通道命名区仍渲染 8 个输入框（NodeEditFormContent 未按 channels 截断）

### 2.3 /devices 设备管理

- 真实设备管理（扫描/连接）、已连接设备、真实EEG设备、设备列表四个分区清晰
- 5 个模拟设备全部列出，状态/采样率/通道数/绑定状态完整
- 侧边栏导航高亮已正确切换（本次新增的导航项工作正常）

### 2.4 /dev 开发目录

- 简洁的两卡片入口（设备管理 / 串口调试），无问题

### 2.5 /dev/serial-debug 串口调试

- 端口筛选、样本数、编码、自动刷新、刷新按钮齐全；空态提示明确

---

## 三、可维护性检查

| 项 | 结论 |
|---|---|
| 巨型组件 | GraphEditor 已拆分出 Toolbar/Palette，但本体仍偏大（后续可继续抽边动画、通道推断） |
| 重复逻辑 | 原 `createDeviceDialogOpen` 与 `deviceFormDialogOpen` 两个新建设备弹窗并存——本次保留（分别服务节点库与设备管理弹窗），建议后续合并 |
| 死代码 | 本次已清除 editDialog / pinnedNodePanel / createNodeHtml / 冗余 drag handler |
| 类型健康 | 新增组件 0 类型错误；存量隐式 any 与 ECharts 类型不匹配为既有技术债 |

---

## 四、问题清单（含既有问题）

| # | 页面 | 位置 | 问题 | 严重级别 | 状态/建议 |
|---|---|---|---|---|---|
| 1 | /cpgraph | applyFrozen | 调用未定义的 connect/disconnectWebSocket，冻结必抛错 | 高 | ✅ 已修复 |
| 2 | /cpgraph | 工具栏 | 缺冻结开关与保存按钮 | 高 | ✅ 已修复 |
| 3 | /cpgraph | GraphEditor | 死代码 editDialog/pinnedNodePanel/createNodeHtml | 中 | ✅ 已清除 |
| 4 | 全局 | Sidebar | 无 /devices 导航 | 中 | ✅ 已修复 |
| 5 | /visualization | Oscilloscope | 未冻结提示仅跳转链接 | 低 | ✅ 已改为内联冻结按钮 |
| 6 | /cpgraph | GraphEditor.vue:2271+ | X6 回调隐式 any、onDragOver/onDrop 作用域 | 低 | 既有，建议后续补类型 |
| 7 | /cpgraph | NodeEditFormContent | 通道命名输入框数量不随 channels 截断 | 低 | 既有，建议修 |
| 8 | /cpgraph | GraphEditor | createDevice 与 deviceForm 两套新建设备弹窗 | 低 | 建议合并 |
| 9 | e2e | graph-editor.spec / sidebar-statusbar.spec | 8 个用例失败（`text=调试示波器`、`[role=switch]` 时序、`[title=录制]` 等） | 中 | **既有**，重构前后失败集一致；与 Sidebar v-tooltip activator 吞掉 title 属性有关，建议独立修复 |

---

## 五、本次落地清单

- 新增 `frontend/src/components/GraphToolbar.vue`
- 新增 `frontend/src/components/GraphPalette.vue`
- 重构 `frontend/src/components/GraphEditor.vue`（拆分子组件、修 ReferenceError、清死代码、修 freeze push 告警）
- 修改 `frontend/src/components/Sidebar.vue`（新增设备管理导航）
- 修改 `frontend/src/App.vue`（删除高度 !important 覆盖）
- 修改 `frontend/src/components/Oscilloscope.vue`（未冻结提示 + 立即冻结按钮）

**回归结论**：vue-tsc 新组件 0 错误；浏览器手工验证通过；e2e 基线对比确认零回归。
