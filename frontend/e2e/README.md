# Playwright E2E 测试

EEG 前端项目的端到端自动化测试。

## 测试覆盖

### 计算图编辑器
- ✅ 页面结构和标题检查
- ✅ 加载 Mock 数据
- ✅ 拖拽创建节点
- ✅ 双击打开节点编辑对话框
- ✅ 编辑节点参数
- ✅ 冻结和运行计算图
- ✅ 清空画布

### 导航和路由
- ✅ 各页面导航切换

## 运行测试

### 安装依赖
```bash
npm install
npx playwright install chromium
```

### 运行所有测试
```bash
npm run test:e2e
```

### 运行带 UI 的测试（调试用）
```bash
npm run test:e2e:ui
```

### 调试模式
```bash
npm run test:e2e:debug
```

### 查看测试报告
```bash
npm run test:e2e:report
```

## 测试截图

测试过程中会自动保存截图到 `e2e/screenshots/` 目录：
- `mock-data-loaded.png` - Mock 数据加载后的状态
- `drag-node.png` - 拖拽创建节点
- `node-edit-dialog.png` - 节点编辑对话框
- `node-edited.png` - 节点编辑后
- `oscilloscope-running.png` - 示波器实时运行
- `canvas-cleared.png` - 清空画布后
- `navigation.png` - 导航切换

## 测试配置

配置文件：`playwright.config.ts`

- 测试目录：`./e2e`
- 基础 URL：`http://localhost:5173`
- 浏览器：Chromium
- 自动启动 dev server

## 编写新测试

参考 `e2e/graph-editor.spec.ts` 的写法：

```typescript
import { test, expect } from '@playwright/test';

test('测试描述', async ({ page }) => {
  await page.goto('/#/cpgraph');
  
  // 执行操作
  await page.click('button:has-text("按钮")');
  
  // 验证结果
  await expect(page.locator('text=期望文本')).toBeVisible();
  
  // 截图
  await page.screenshot({ path: 'e2e/screenshots/test.png' });
});
```

## CI/CD 集成

可以在 GitHub Actions 中运行：

```yaml
- name: Run Playwright tests
  run: |
    npm install
    npx playwright install chromium
    npm run test:e2e
```
