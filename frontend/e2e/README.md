# EEG系统Playwright测试

## 测试结构

```
e2e/
├── eeg-system.spec.ts    # 主测试文件
├── graph-editor.spec.ts  # 原有测试
├── screenshots/          # 测试截图
└── README.md            # 本文档
```

## 测试覆盖

### 1. 计算图编辑器测试
- ✅ 页面基本结构
- ✅ 加载计算图
- ✅ 冻结开关功能
- ✅ 保存计算图（持久化验证）
- ✅ 双击编辑节点

### 2. 示波器测试
- ✅ 基本结构验证
- ✅ 绑定OSC节点
- ✅ 解除绑定
- ✅ 性能测试（内存不无限增长）

### 3. 设备列表测试
- ✅ 基本结构
- ✅ 绑定设备到SOURCE节点

### 4. 端到端流程测试
- ✅ 完整数据流：冻结 -> 绑定 -> 显示波形
- ✅ 解冻后停止数据流

### 5. 性能和稳定性测试
- ✅ 页面加载性能
- ✅ 长时间运行稳定性（10秒）

## 运行测试

### 前提条件
确保后端和前端的Docker容器正在运行：
```bash
docker ps | grep eeg
```

### 运行所有测试
```bash
npm run test:e2e
```

### 运行特定测试文件
```bash
npx playwright test e2e/eeg-system.spec.ts
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

## 测试截图

测试运行后，截图保存在 `e2e/screenshots/` 目录：
- `graph-editor-basic.png` - 计算图编辑器基本结构
- `graph-mock-loaded.png` - Mock数据加载后
- `graph-freeze-toggle.png` - 冻结开关切换
- `osc-bound.png` - 示波器绑定后
- `e2e-full-flow.png` - 完整端到端流程

## 故障排除

### 测试失败：元素不可见
- 增加 `waitForTimeout` 时间
- 检查后端服务是否运行

### 测试失败：WebSocket未连接
- 确保计算图已冻结
- 检查 `ws://localhost:8000/ws/eeg/` 是否可访问

### 截图为空
- 确保页面完全加载
- 检查是否有JavaScript错误

## 更新测试

当功能变更时，更新对应测试：
1. 修改 `e2e/eeg-system.spec.ts`
2. 运行测试验证：`npm run test:e2e`
3. 提交更新
