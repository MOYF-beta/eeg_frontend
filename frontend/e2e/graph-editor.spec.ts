import { test, expect } from '@playwright/test';

test.describe('计算图编辑器', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test('加载计算图并截图', async ({ page }) => {
    await page.waitForTimeout(1500);
    
    await expect(page.locator('text=调试示波器')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/01-graph-loaded.png', fullPage: true });
  });

  test('冻结开关切换', async ({ page }) => {
    await page.waitForTimeout(1000);
    
    const runButton = page.locator('button:has-text("运行")');
    await expect(runButton).toBeDisabled();
    
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    await expect(runButton).toBeEnabled();
    
    await page.screenshot({ path: 'e2e/screenshots/02-frozen.png', fullPage: true });
  });

  test('保存计算图持久化', async ({ page }) => {
    await page.waitForTimeout(1000);
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    await page.click('button:has-text("保存")');
    await page.waitForTimeout(1000);
    
    await page.reload();
    await page.waitForTimeout(2000);
    
    await expect(page.locator('button:has-text("运行")')).toBeEnabled();
    
    await page.screenshot({ path: 'e2e/screenshots/03-saved-persist.png', fullPage: true });
  });

  test('双击编辑节点', async ({ page }) => {
    await page.waitForTimeout(1000);
    
    await page.dblclick('text=调试示波器');
    await page.waitForTimeout(500);
    
    await expect(page.locator('text=编辑节点')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/04-edit-dialog.png' });
  });
});

test.describe('示波器', () => {
  test('绑定输出节点显示波形', async ({ page }) => {
    // 设置计算图
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 切换到显示与录制
    await page.click('text=显示与录制');
    await page.waitForTimeout(1000);
    
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=显示与录制');
    await page.waitForTimeout(3000);
    
    await expect(page.locator('text=接收中')).toBeVisible();
    
    const packetText = await page.locator('text=/接收: \\d+ 包/').textContent();
    expect(packetText).toMatch(/接收: \d+ 包/);
    
    await page.screenshot({ path: 'e2e/screenshots/05-oscilloscope.png', fullPage: true });
  });
});

test.describe('端到端流程', () => {
  test('完整数据流', async ({ page }) => {
    // 1. 计算图
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.click('button:has-text("清空")');
    await page.waitForTimeout(500);
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 2. 绑定设备
    await page.click('text=设备');
    await page.waitForTimeout(1000);
    await page.click('.v-select').first();
    await page.waitForTimeout(500);
    await page.click('text=模拟设备_1');
    await page.waitForTimeout(1000);
    
    // 3. 显示与录制
    await page.click('text=显示与录制');
    await page.waitForTimeout(1000);
    await page.click('.v-select');
    await page.waitForTimeout(500);
    await page.click('text=显示与录制');
    await page.waitForTimeout(3000);
    
    await expect(page.locator('text=接收中')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/06-e2e-flow.png', fullPage: true });
  });
});
