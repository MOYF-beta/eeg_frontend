# UI 设计文档

本文档定义三个核心页面的UI元素清单，遵循实用优先原则，使用Vuetify组件库。

---

## 1. 主页（设备管理）

### 1.1 顶部工具栏
- **标题**: "脑电采集系统"（v-toolbar-title）
- **添加设备按钮**: 
  - 图标: mdi-plus
  - 文本: "添加设备"
  - 点击弹出菜单：
    - "物理设备"（禁用，灰色）
    - "模拟信号源"

### 1.2 设备列表区域
**容器**: v-container，使用网格布局

每个设备一个卡片（v-card）：

#### 卡片头部（v-card-title）
- **左侧**:
  - 设备名称（可编辑，点击变为输入框）
  - 设备地址（小字，灰色）
  - 设备类型标签（v-chip，simulated显示蓝色）
- **右侧**:
  - 连接状态指示灯（v-icon circle，绿/红/灰）
  - 电池电量（v-icon battery + 百分比文字）
  - 删除按钮（v-btn icon，mdi-delete）

#### 卡片内容（v-card-text）
**左栏（60%宽度）**:
- 通道配置表格（v-simple-table）
  - 列：通道号 | 助记名 | 阻抗 | 状态
  - 助记名可编辑（点击变输入框）
  - 阻抗显示数值 + 单位（kΩ）
  - 状态用颜色圆点表示（绿/黄/红）
  
**右栏（40%宽度）**:
- 波形缩略图（ECharts，高度200px）
  - 显示所有通道叠加
  - 仅显示最近2秒数据
  - 无坐标轴标签
  - 通道选择器（v-checkbox-group，紧凑显示）

#### 卡片底部（v-card-actions）
- **配置按钮**: "通道配置"（弹出对话框）
- **查看按钮**: "查看数据"（跳转到可视化页面，自动选中该设备）

### 1.3 添加设备对话框（v-dialog）

#### 模拟信号源表单
- **设备名称**: v-text-field
- **采样率**: v-select（选项：250/500/1000 Hz）
- **通道数**: v-select（选项：4/8/16）
- **通道配置列表**:
  - 每行一个通道（v-expansion-panels）
    - 面板标题：通道号 + 助记名
    - 展开内容：
      - 助记名输入框
      - 波形类型：v-radio-group（正弦波/方波/三角波）
      - 频率：v-slider（1-100 Hz）
      - 幅度：v-slider（1-500 uV）
- **操作按钮**:
  - 取消（v-btn text）
  - 创建（v-btn color="primary"）

---

## 2. 可视化页面

### 2.1 顶部控制栏
**容器**: v-toolbar，dense

- **设备选择器**: 
  - v-select（单选模式）
  - 显示：设备名称 + 地址
  - 右侧显示采样率（只读文本，灰色）

- **布局切换**:
  - v-btn-toggle（单选）
    - 选项：单列 | 双列 | 网格
  
- **添加卡片按钮**:
  - v-menu（下拉菜单）
  - 图标: mdi-plus-box
  - 选项：
    - "添加示波器"
    - "添加频谱图"

- **全局控制**:
  - 暂停/继续按钮（v-btn icon，mdi-pause/mdi-play）
  - 录制按钮（v-btn color="red"，圆形，闪烁动画当录制中）
  - 录制时长显示（文本，格式：00:00:00）

### 2.2 卡片栅格区域
**容器**: v-row + v-col（响应式列数）

#### 2.2.1 示波器卡片（v-card）

**卡片标题栏（v-card-title）**:
- **左侧**:
  - 设备名称
  - 显示窗口时长（如"10.0s"）
- **右侧**:
  - 截图按钮（v-btn icon，mdi-camera）
  - 重置统计按钮（v-btn icon，mdi-refresh）
  - 删除卡片按钮（v-btn icon，mdi-close）

**卡片内容（v-card-text）**:
- **左侧通道控制区（宽度120px，固定）**:
  - 通道列表（v-list，dense）
    - 每个通道一行：
      - 复选框（显示/隐藏该通道）
      - 通道名称
      - 颜色块（10x10px）
      - 幅度调节滑块（垂直，紧凑）
        - 范围：0.1x - 10x
        - 默认：1x
  
  - 全局控制组：
    - 全选/全不选（v-checkbox）
    - 窗口时长滑块（v-slider）
      - 范围：1-30秒
      - 步进：1秒
    - 刷新率选择（v-select）
      - 选项：10fps/25fps/60fps

- **右侧图表区（flex: 1）**:
  - ECharts 容器（高度：每通道60px + 边距）
    - X轴：时间（秒）
    - Y轴：每个通道独立一行
    - 显示通道名称标签（左侧）
    - 网格线：浅灰色虚线
    - 背景色：#1a1a1a（深色）
    - 曲线颜色：使用预设调色板
  
  - 统计曲线图层（可开关）：
    - 窗口最大值（红色虚线）
    - 窗口最小值（蓝色虚线）
    - 窗口平均值（黄色虚线）
    - 全局最大值（红色实线）
    - 全局最小值（蓝色实线）
    - 全局平均值（黄色实线）

**卡片底部（v-card-actions）**:
- 统计信息文本（小字）：
  - 当前采样点数
  - 数据缓冲区大小（MB）
- 统计显示开关（v-switch）:
  - "显示窗口统计"
  - "显示全局统计"

#### 2.2.2 频谱图卡片（v-card）

**卡片标题栏**:
- 同示波器卡片
- 额外显示：FFT窗口大小（如"512点"）

**卡片内容**:
- **左侧通道控制区（同示波器）**:
  - 通道复选框列表
  - 幅度控制滑块
  
  - 频谱设置：
    - FFT窗口：v-select（256/512/1024/2048）
    - 更新速率：v-select（1Hz/5Hz/10Hz）
    - 频率范围：v-range-slider
      - 最小：0 Hz
      - 最大：采样率/2
    - Y轴模式：v-radio-group
      - 线性
      - 对数（dB）

- **右侧图表区**:
  - ECharts 容器（高度400px）
    - X轴：频率（Hz）
    - Y轴：幅度（uV 或 dB）
    - 每个通道一条曲线
    - 图例（顶部，可点击隐藏）
  
  - 统计曲线（可选）：
    - 所有通道最大值包络（红色半透明）
    - 所有通道最小值包络（蓝色半透明）
    - 平均功率谱（黄色粗线）

**卡片底部**:
- 主频标注（文本）：
  - 格式："CH1: 10.2Hz | CH2: 9.8Hz | ..."

### 2.3 空状态提示
- 当没有卡片时显示：
  - v-empty-state（Vuetify 3.x）
  - 图标：mdi-chart-line-variant
  - 文本："点击上方按钮添加可视化组件"

---

## 3. 计算图编辑器页面

### 3.1 顶部工具栏
- **左侧**:
  - 计算图名称（可编辑，v-text-field，inline样式）
  - 保存按钮（v-btn，mdi-content-save）
  - 加载按钮（v-btn，mdi-folder-open，弹出对话框）

- **中间**:
  - 执行模式切换（v-btn-toggle）:
    - 实时模式
    - 批处理模式
  - 运行按钮（v-btn color="success"，large）
    - 图未冻结时禁用
  - 停止按钮（v-btn color="error"）
    - 未运行时禁用

- **右侧**:
  - 冻结/解冻图（v-switch）
  - 验证按钮（v-btn，检查图是否有效）
  - 清空画布（v-btn color="error"，mdi-delete-forever）

### 3.2 左侧节点面板（v-navigation-drawer，宽度250px）

**面板标题**: "节点库"

**节点分类**（v-expansion-panels，accordion模式）:

#### 数据源节点
- 实时设备（v-list-item，可拖拽）
  - 图标：mdi-access-point
- 录制文件（v-list-item，可拖拽）
  - 图标：mdi-file

#### 处理节点
- 高通滤波器（mdi-filter-variant）
- 低通滤波器（mdi-filter-variant）
- 带通滤波器（mdi-filter）
- 求和器（mdi-math-norm）
- 通道分离器（mdi-call-split）
- 通道合并器（mdi-call-merge）

#### 输出节点
- 示波器（mdi-waveform）
- 频谱显示器（mdi-chart-areaspline）
- 保存节点（mdi-content-save）

**使用提示**（v-card，底部固定）:
- 文本：
  - "拖拽节点到画布"
  - "双击节点配置参数"
  - "连线形成计算流程"

### 3.3 中央画布区域

**容器**: AntV X6 Graph容器（#graph-container，占满剩余空间）

**画布工具栏**（悬浮在画布左上角，v-speed-dial）:
- 缩放：
  - 放大（v-btn icon，mdi-plus）
  - 缩小（v-btn icon，mdi-minus）
  - 适应画布（v-btn icon，mdi-fit-to-page）
- 对齐：
  - 水平对齐（v-btn icon）
  - 垂直对齐（v-btn icon）
  - 分布排列（v-btn icon）
- 撤销/重做（v-btn icon）

**节点样式设计**:

所有节点基础样式：
- 宽度：180px
- 高度：60px
- 圆角：4px
- 边框：2px solid
- 阴影：轻微阴影

节点结构（上中下布局）：
- **顶部栏（高度20px）**:
  - 图标（左侧，16x16）
  - 节点类型名称（中间，12px字体）
  - 配置按钮（右侧，mdi-cog，仅处理节点）
  
- **中部内容区（高度30px）**:
  - 节点ID（粗体，14px）
  - 简要参数显示（如"cutoff: 0.5Hz"）
  
- **底部连接点区**:
  - 输入端口（左侧，圆形，8px直径）
  - 输出端口（右侧，圆形，8px直径）

节点颜色方案：
- 数据源：蓝色（#2196F3）
- 处理节点：绿色（#4CAF50）
- 输出节点：橙色（#FF9800）
- 选中状态：边框变粗，加深颜色

**连线样式**:
- 默认：灰色（#9E9E9E），2px宽
- 选中：蓝色（#2196F3），3px宽
- 箭头：实心三角形

### 3.4 右侧属性面板（v-navigation-drawer，宽度300px）

**面板标题**: "属性配置"

**未选中任何节点时**:
- 显示空状态
- 提示："选择节点以配置参数"

**选中节点时，显示节点表单**:

#### 数据源节点表单
**实时设备**:
- 设备选择（v-select）
- 通道选择（v-select，multiple，chips）

**录制文件**:
- 文件路径（v-text-field，带浏览按钮）
- 时间范围（v-range-slider）
  - 最小值：0
  - 最大值：文件总时长
  - 显示格式化时间

#### 滤波器节点表单
- 截止频率（v-text-field，type="number"）
  - 单位：Hz
  - 验证：> 0，< 采样率/2
- 滤波器阶数（v-slider）
  - 范围：1-8
  - 默认：4
- 实时预览（v-switch）

#### 求和器节点表单
- 操作类型（v-radio-group）:
  - 求和
  - 求平均
  - 加权和
- 权重配置（仅加权和时显示）:
  - 动态生成输入框列表

#### 通道分离器表单
- 通道组配置（v-textarea）
  - 格式提示："1,2-3,4 表示第1组、2-3组、第4组"
  - 实时解析和验证
- 输出组列表（v-chip-group，显示解析结果）

#### 通道合并器表单
- 合并方式（v-radio-group）:
  - 按通道顺序
  - 自定义顺序
- 通道重命名（v-data-table，可编辑）

#### 示波器节点表单
- 窗口时长（v-slider，1-30秒）
- 缓冲区大小（v-select，MB）

#### 频谱显示器节点表单
- FFT窗口（v-select）
- 频率范围（v-range-slider）

#### 保存节点表单
- 文件名（v-text-field）
- 文件格式（v-select）:
  - CSV
  - MAT
  - EDF（禁用）
- 保存通道（v-select，multiple）
- 自动分段（v-switch）
  - 分段大小（v-text-field，仅自动分段时显示）

**通用操作按钮**（面板底部）:
- 应用配置（v-btn color="primary"，block）
- 重置为默认（v-btn text，block）

### 3.5 底部状态栏（v-footer，高度40px）

- **左侧**:
  - 节点数量："节点: 5 | 连线: 4"
  - 验证状态：
    - 图标（mdi-check-circle绿色 或 mdi-alert-circle红色）
    - 文本（"图有效" 或 错误信息）

- **中间**:
  - 执行状态（仅运行时显示）:
    - 进度条（v-progress-linear，indeterminate模式）
    - 文本："处理中... 45.2s"

- **右侧**:
  - 画布缩放比例："100%"
  - 鼠标位置（调试用）:"(120, 340)"

### 3.6 执行配置对话框（v-dialog）

**批处理模式配置**:
- 数据源选择（v-radio-group）:
  - 实时设备（需要选择时间范围）
  - 录制文件
- 文件选择（v-file-input）
- 时间范围（v-range-slider）
- 输出目录（v-text-field，带浏览按钮）

**实时模式配置**:
- 数据源：仅支持实时设备
- 缓冲设置（v-slider，秒）

**操作按钮**:
- 取消
- 开始执行

---

## 4. 通用组件

### 4.1 全局顶部导航栏（v-app-bar）

- **左侧**:
  - 菜单按钮（mdi-menu，切换侧边导航）
  - 应用名称："脑电采集系统"
  
- **右侧**:
  - WebSocket连接状态（v-chip，small）
    - 已连接：绿色，mdi-check-network
    - 未连接：红色，mdi-close-network
  - 全局录制指示（v-chip，仅录制时显示）
    - 红色闪烁
    - 文本："录制中"
  - 设置按钮（v-btn icon，mdi-cog）
  - 帮助按钮（v-btn icon，mdi-help-circle）

### 4.2 侧边导航抽屉（v-navigation-drawer）

**导航列表**（v-list）:
- 主页（mdi-home）
- 可视化（mdi-chart-line）
- 计算图（mdi-graph）
- 录制管理（mdi-database）
- 设置（mdi-cog）

**底部信息**:
- 版本号（v-list-item，disabled）
- 关于（v-list-item，点击弹出对话框）

### 4.3 通知系统（v-snackbar）

**显示位置**: 顶部右侧
**自动关闭**: 3秒（错误5秒）

**类型**:
- 成功：绿色，mdi-check-circle
- 警告：橙色，mdi-alert
- 错误：红色，mdi-alert-circle
- 信息：蓝色，mdi-information

### 4.4 确认对话框（v-dialog）

**标准结构**:
- 标题（v-card-title）
- 内容（v-card-text）
- 操作按钮（v-card-actions）:
  - 取消（v-btn text）
  - 确认（v-btn color根据危险程度：primary/error）

**使用场景**:
- 删除设备
- 删除卡片
- 清空画布
- 停止执行

---

## 5. 响应式设计

### 5.1 断点定义（Vuetify标准）
- xs: <600px（手机）
- sm: 600-960px（小平板）
- md: 960-1264px（平板/小笔记本）
- lg: 1264-1904px（桌面）
- xl: >1904px（大屏）

### 5.2 适配策略

**主页设备列表**:
- xs/sm: 单列
- md: 双列
- lg/xl: 三列

**可视化页面卡片**:
- xs: 单列，强制
- sm: 单列或双列（用户可选）
- md/lg/xl: 单列/双列/网格（用户可选）

**计算图编辑器**:
- xs/sm: 隐藏左右面板，改用底部抽屉
- md+: 正常三栏布局

---

## 6. 颜色方案

### 6.1 主题色
- Primary: #1976D2（蓝色）
- Secondary: #424242（深灰）
- Success: #4CAF50（绿色）
- Warning: #FF9800（橙色）
- Error: #F44336（红色）

### 6.2 图表颜色（8通道预设）
1. #E91E63（粉红）
2. #9C27B0（紫色）
3. #2196F3（蓝色）
4. #00BCD4（青色）
5. #4CAF50（绿色）
6. #FFEB3B（黄色）
7. #FF9800（橙色）
8. #F44336（红色）

### 6.3 状态颜色
- 连接良好：#4CAF50（绿）
- 警告：#FF9800（橙）
- 错误/断开：#F44336（红）
- 禁用：#9E9E9E（灰）

---

## 7. 图标映射表

| 功能 | 图标 |
|------|------|
| 添加 | mdi-plus |
| 删除 | mdi-delete |
| 编辑 | mdi-pencil |
| 保存 | mdi-content-save |
| 加载 | mdi-folder-open |
| 设置 | mdi-cog |
| 播放 | mdi-play |
| 暂停 | mdi-pause |
| 停止 | mdi-stop |
| 录制 | mdi-record |
| 设备 | mdi-access-point |
| 通道 | mdi-waveform |
| 滤波器 | mdi-filter-variant |
| 图表 | mdi-chart-line |
| 频谱 | mdi-chart-areaspline |
| 连接 | mdi-link-variant |
| 断开 | mdi-link-variant-off |
| 刷新 | mdi-refresh |
| 截图 | mdi-camera |
| 帮助 | mdi-help-circle |
| 警告 | mdi-alert |
| 错误 | mdi-alert-circle |
| 成功 | mdi-check-circle |

---

## 8. 组件优先级清单

### P0（必须实现）
- 设备列表卡片
- 示波器卡片
- WebSocket连接状态显示
- 基础导航

### P1（核心功能）
- 频谱图卡片
- 计算图画布
- 节点配置面板
- 录制控制

### P2（增强体验）
- 统计曲线显示
- 响应式布局
- 通知系统
- 键盘快捷键

### P3（可选）
- 暗色主题切换
- 自定义颜色
- 导出配置
- 历史记录

---

本文档提供所有页面的UI元素清单，可直接用于组件开发。