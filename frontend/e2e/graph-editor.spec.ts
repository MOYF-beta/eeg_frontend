import { test, expect } from '@playwright/test';

test.describe('EEG 计算图编辑器', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/#/cpgraph');
    await page.waitForLoadState('networkidle');
  });

  test('页面标题和基本结构', async ({ page }) => {
    // 检查页面标题
    await expect(page.locator('h1')).toContainText('计算图');
    
    // 检查编辑器标题
    await expect(page.locator('text=计算图编辑器')).toBeVisible();
    
    // 检查工具栏按钮
    await expect(page.locator('button:has-text("保存")')).toBeVisible();
    await expect(page.locator('button:has-text("运行")')).toBeVisible();
    await expect(page.locator('button:has-text("加载Mock")')).toBeVisible();
    await expect(page.locator('button:has-text("清空")')).toBeVisible();
    
    // 检查节点库
    await expect(page.locator('text=节点库')).toBeVisible();
    await expect(page.locator('text=数据来源')).toBeVisible();
    await expect(page.locator('text=处理节点')).toBeVisible();
    await expect(page.locator('text=显示与保存')).toBeVisible();
  });

  test('加载 Mock 数据', async ({ page }) => {
    // 点击加载Mock按钮
    await page.click('button:has-text("加载Mock")');
    
    // 等待节点渲染
    await page.waitForTimeout(1000);
    
    // 检查节点是否显示
    await expect(page.locator('text=脑电数据源')).toBeVisible();
    await expect(page.locator('text=低通滤波器')).toBeVisible();
    await expect(page.locator('text=通道分离')).toBeVisible();
    await expect(page.locator('text=波形显示器')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/mock-data-loaded.png' });
  });

  test('节点拖拽创建', async ({ page }) => {
    // 获取画布区域
    const canvas = page.locator('.graph-container');
    await expect(canvas).toBeVisible();
    
    // 拖拽数据源节点到画布
    const sourceNode = page.locator('.palette-item:has-text("数据源")').first();
    await sourceNode.dragTo(canvas, {
      targetPosition: { x: 200, y: 200 },
    });
    
    // 等待节点创建
    await page.waitForTimeout(500);
    
    // 检查节点是否创建成功（通过计数）
    const nodes = page.locator('.x6-node');
    await expect(nodes).toHaveCount(1);
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/drag-node.png' });
  });

  test('双击节点打开编辑对话框', async ({ page }) => {
    // 先加载Mock数据
    await page.click('button:has-text("加载Mock")');
    await page.waitForTimeout(1000);
    
    // 双击低通滤波器节点
    await page.dblclick('text=低通滤波器');
    
    // 等待对话框打开
    await page.waitForTimeout(500);
    
    // 检查对话框内容
    await expect(page.locator('text=编辑节点: 低通滤波器')).toBeVisible();
    await expect(page.locator('text=滤波器类型')).toBeVisible();
    await expect(page.locator('text=截止频率')).toBeVisible();
    await expect(page.locator('text=阶数')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/node-edit-dialog.png' });
    
    // 关闭对话框
    await page.click('button:has-text("取消")');
  });

  test('编辑节点参数', async ({ page }) => {
    // 加载Mock数据
    await page.click('button:has-text("加载Mock")');
    await page.waitForTimeout(1000);
    
    // 双击低通滤波器节点
    await page.dblclick('text=低通滤波器');
    await page.waitForTimeout(500);
    
    // 修改节点名称
    await page.fill('input[label="节点名称"]', '高通滤波器');
    
    // 修改截止频率
    await page.fill('input[type="number"]', '100');
    
    // 保存
    await page.click('button:has-text("保存")');
    await page.waitForTimeout(500);
    
    // 验证节点名称已更新
    await expect(page.locator('text=高通滤波器')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/node-edited.png' });
  });

  test('冻结和运行计算图', async ({ page }) => {
    // 加载Mock数据
    await page.click('button:has-text("加载Mock")');
    await page.waitForTimeout(1000);
    
    // 点击冻结开关
    await page.click('.v-switch');
    await page.waitForTimeout(500);
    
    // 检查运行按钮是否启用
    const runButton = page.locator('button:has-text("运行")');
    await expect(runButton).toBeEnabled();
    
    // 点击运行
    await runButton.click();
    await page.waitForTimeout(1000);
    
    // 切换到示波器页面
    await page.click('text=示波器');
    await page.waitForTimeout(2000);
    
    // 检查示波器是否显示波形
    await expect(page.locator('canvas')).toBeVisible();
    await expect(page.locator('text=在线')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/oscilloscope-running.png' });
  });

  test('清空画布', async ({ page }) => {
    // 加载Mock数据
    await page.click('button:has-text("加载Mock")');
    await page.waitForTimeout(1000);
    
    // 检查节点存在
    await expect(page.locator('text=脑电数据源')).toBeVisible();
    
    // 点击清空
    await page.click('button:has-text("清空")');
    await page.waitForTimeout(500);
    
    // 检查提示文本显示（表示画布为空）
    await expect(page.locator('text=从左侧拖拽节点到此处')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/canvas-cleared.png' });
  });
});

test.describe('导航和路由', () => {
  test('导航到各页面', async ({ page }) => {
    // 设备页面
    await page.click('text=设备');
    await page.waitForTimeout(500);
    await expect(page.locator('text=设备管理')).toBeVisible();
    
    // 示波器页面
    await page.click('text=示波器');
    await page.waitForTimeout(500);
    await expect(page.locator('text=波形可视化')).toBeVisible();
    
    // 计算图页面
    await page.click('text=计算图');
    await page.waitForTimeout(500);
    await expect(page.locator('text=计算图编辑器')).toBeVisible();
    
    // 截图保存
    await page.screenshot({ path: 'e2e/screenshots/navigation.png' });
  });
});
