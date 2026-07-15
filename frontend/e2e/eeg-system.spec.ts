import { test, expect } from '@playwright/test';

/**
 * EEG系统前端完整测试套件
 * 
 * 测试范围：
 * 1. 计算图编辑器 - 节点操作、冻结/运行、保存
 * 2. 示波器 - 数据绑定、波形显示、性能
 * 3. 设备列表 - 绑定/解绑、配置
 * 4. 端到端流程 - 完整数据流测试
 */

// ==================== 计算图编辑器测试 ====================
test.describe('计算图编辑器', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test('页面基本结构', async ({ page }) => {
    await expect(page.locator('text=计算图编辑器')).toBeVisible();
    await expect(page.locator('text=节点库')).toBeVisible();
    await expect(page.locator('button:has-text("保存")')).toBeVisible();
    await expect(page.locator('button:has-text("运行")')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/graph-editor-basic.png' });
  });

  test('加载计算图', async ({ page }) => {
    await page.waitForTimeout(1500);
    
    // 验证节点显示（从后端加载）
    await expect(page.locator('text=调试示波器')).toBeVisible();
    await expect(page.locator('text=滤波器')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/graph-mock-loaded.png' });
  });

  test('冻结开关功能', async ({ page }) => {
    await page.waitForTimeout(1000);
    
    // 初始状态：运行按钮禁用
    const runButton = page.locator('button:has-text("运行")');
    await expect(runButton).toBeDisabled();
    
    // 点击冻结开关
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 运行按钮应启用
    await expect(runButton).toBeEnabled();
    
    // 再次点击解冻
    await page.click('[role="switch"]');
    await page.waitForTimeout(500);
    
    await expect(runButton).toBeDisabled();
    
    await page.screenshot({ path: 'e2e/screenshots/graph-freeze-toggle.png' });
  });

  test('保存计算图', async ({ page }) => {
    await page.waitForTimeout(1000);
    
    // 冻结
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 保存
    await page.click('button:has-text("保存")');
    await page.waitForTimeout(1000);
    
    // 刷新页面
    await page.reload();
    await page.waitForTimeout(2000);
    
    // 验证冻结状态保持
    await expect(page.locator('button:has-text("运行")')).toBeEnabled();
    
    await page.screenshot({ path: 'e2e/screenshots/graph-save-persist.png' });
  });

  test('双击编辑节点', async ({ page }) => {
    await page.waitForTimeout(1000);
    
    // 双击节点
    await page.dblclick('text=滤波器');
    await page.waitForTimeout(500);
    
    // 验证编辑对话框
    await expect(page.locator('text=编辑节点')).toBeVisible();
    await expect(page.locator('text=截止频率')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/graph-edit-dialog.png' });
  });
});

// ==================== 示波器测试 ====================
test.describe('示波器', () => {
  test.beforeEach(async ({ page }) => {
    // 先设置计算图
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]'); // 冻结
    await page.waitForTimeout(1000);
    
    // 切换到示波器页面
    await page.click('text=示波器');
    await page.waitForTimeout(1000);
  });

  test('示波器基本结构', async ({ page }) => {
    await expect(page.locator('text=波形可视化')).toBeVisible();
    await expect(page.locator('text=选择数据源')).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/osc-basic.png' });
  });

  test('绑定输出节点', async ({ page }) => {
    // 打开选择下拉框
    await page.click('.v-select');
    await page.waitForTimeout(500);
    
    // 选择输出节点
    await page.click('text=调试示波器');
    await page.waitForTimeout(2000);
    
    // 验证状态变为接收中
    await expect(page.locator('text=接收中')).toBeVisible();
    
    // 验证数据包计数增加
    const packetText = await page.locator('text=/接收: \\d+ 包/').textContent();
    expect(packetText).toMatch(/接收: \d+ 包/);
    
    await page.screenshot({ path: 'e2e/screenshots/osc-bound.png' });
  });

  test('解除绑定', async ({ page }) => {
    // 先绑定
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=调试示波器');
    await page.waitForTimeout(2000);
    
    // 验证已绑定
    await expect(page.locator('text=接收中')).toBeVisible();
    
    // 点击解除绑定
    await page.click('button:has-text("解除绑定")');
    await page.waitForTimeout(1000);
    
    // 验证回到未选择状态
    await expect(page.locator('text=请选择数据源')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/osc-unbound.png' });
  });

  test('性能 - 数据不无限增长', async ({ page }) => {
    // 绑定输出节点
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=调试示波器');
    await page.waitForTimeout(5000); // 等待5秒收集数据
    
    // 获取内存使用情况
    const memory = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });
    
    console.log(`Memory usage after 5s: ${(memory / 1024 / 1024).toFixed(2)} MB`);
    
    // 再等待5秒
    await page.waitForTimeout(5000);
    
    const memory2 = await page.evaluate(() => {
      return (performance as any).memory?.usedJSHeapSize || 0;
    });
    
    console.log(`Memory usage after 10s: ${(memory2 / 1024 / 1024).toFixed(2)} MB`);
    
    // 内存增长应该有限（小于50MB）
    const growth = (memory2 - memory) / 1024 / 1024;
    expect(growth).toBeLessThan(50);
    
    await page.screenshot({ path: 'e2e/screenshots/osc-performance.png' });
  });
});

// ==================== 设备列表测试 ====================
test.describe('设备列表', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/devices?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test('设备列表基本结构', async ({ page }) => {
    await expect(page.locator('text=设备列表')).toBeVisible();
    await expect(page.locator('button:has-text("刷新")')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/devices-basic.png' });
  });

  test('绑定设备到SOURCE节点', async ({ page }) => {
    // 选择计算图节点
    await page.click('.v-select').first();
    await page.waitForTimeout(500);
    
    // 选择SOURCE节点
    await page.click('text=脑电数据源');
    await page.waitForTimeout(1000);
    
    // 验证绑定成功
    await expect(page.locator('text=已绑定到')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/devices-bound.png' });
  });
});

// ==================== 端到端流程测试 ====================
test.describe('端到端数据流', () => {
  test('完整流程：冻结 -> 绑定 -> 显示波形', async ({ page }) => {
    // 1. 计算图页面 - 加载并冻结
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    await page.click('button:has-text("保存")');
    await page.waitForTimeout(1000);
    
    // 2. 设备页面 - 绑定设备
    await page.click('text=设备');
    await page.waitForTimeout(1000);
    await page.click('.v-select').first();
    await page.waitForTimeout(500);
    await page.click('text=模拟设备_1');
    await page.waitForTimeout(1000);
    
    // 3. 示波器页面 - 绑定并查看波形
    await page.click('text=示波器');
    await page.waitForTimeout(1000);
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=调试示波器');
    await page.waitForTimeout(3000);
    
    // 验证波形显示
    await expect(page.locator('text=接收中')).toBeVisible();
    await expect(page.locator('canvas')).toBeVisible();
    
    // 验证数据包计数
    const packetText = await page.locator('text=/接收: \\d+ 包/').textContent();
    const match = packetText?.match(/(\d+)/);
    const packetCount = match ? parseInt(match[1]) : 0;
    expect(packetCount).toBeGreaterThan(100); // 至少100个数据包
    
    await page.screenshot({ path: 'e2e/screenshots/e2e-full-flow.png' });
  });

  test('解冻后停止数据流', async ({ page }) => {
    // 先设置并冻结
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 绑定示波器
    await page.click('text=示波器');
    await page.waitForTimeout(1000);
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=波形显示器');
    await page.waitForTimeout(3000);
    
    // 记录当前数据包数
    const packetText1 = await page.locator('text=/接收: \\d+ 包/').textContent();
    const match1 = packetText1?.match(/(\d+)/);
    const count1 = match1 ? parseInt(match1[1]) : 0;
    
    // 返回计算图并解冻
    await page.click('text=计算图');
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]'); // 解冻
    await page.waitForTimeout(1000);
    
    // 回到示波器
    await page.click('text=示波器');
    await page.waitForTimeout(3000);
    
    // 验证数据包不再增加（或增加很少）
    const packetText2 = await page.locator('text=/接收: \\d+ 包/').textContent();
    const match2 = packetText2?.match(/(\d+)/);
    const count2 = match2 ? parseInt(match2[1]) : 0;
    
    // 3秒内增加不超过10个包
    expect(count2 - count1).toBeLessThanOrEqual(10);
    
    await page.screenshot({ path: 'e2e/screenshots/e2e-stop-on-unfreeze.png' });
  });
});

// ==================== 性能和稳定性测试 ====================
test.describe('性能和稳定性', () => {
  test('页面加载性能', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    console.log(`Page load time: ${loadTime}ms`);
    
    // 页面加载应在3秒内完成
    expect(loadTime).toBeLessThan(3000);
  });

  test('长时间运行稳定性', async ({ page }) => {
    // 设置计算图
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 绑定示波器
    await page.click('text=示波器');
    await page.waitForTimeout(1000);
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=调试示波器');
    
    // 运行10秒
    await page.waitForTimeout(10000);
    
    // 验证仍在接收数据
    await expect(page.locator('text=接收中')).toBeVisible();
    
    // 验证数据包计数
    const packetText = await page.locator('text=/接收: \\d+ 包/').textContent();
    const match = packetText?.match(/(\d+)/);
    const packetCount = match ? parseInt(match[1]) : 0;
    
    // 10秒应该接收约10000个包（1000Hz）
    expect(packetCount).toBeGreaterThan(8000);
    
    console.log(`Packets received in 10s: ${packetCount}`);
    
    await page.screenshot({ path: 'e2e/screenshots/stability-10s.png' });
  });
});
