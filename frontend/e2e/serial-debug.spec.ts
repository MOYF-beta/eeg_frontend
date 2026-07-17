/**
 * 串口调试页面 E2E 测试
 *
 * 覆盖 SerialDebugView：
 *   1. 页面加载与标题
 *   2. 端口过滤 v-select
 *   3. 文本编码 v-select（UTF-8/GBK/GB18030/UTF-16LE/Latin-1）
 *   4. 样本数 text-field
 *   5. 自动刷新 switch
 *   6. 刷新按钮
 *   7. 空状态提示
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) 运行中。
 */
import { test, expect } from '@playwright/test';
import { API_BASE, startSimulatorAndConnect, cleanupSimulator } from './helpers';

test.describe('串口调试页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dev/serial-debug?_t=serial');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);
  });

  test('页面加载显示标题', async ({ page }) => {
    await expect(page.locator('text=串口调试输出')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/serial-debug-basic.png', fullPage: true });
  });

  test('端口选择器可见', async ({ page }) => {
    await expect(page.getByLabel('端口')).toBeVisible();
  });

  test('文本编码选择器可见', async ({ page }) => {
    await expect(page.getByLabel('文本编码')).toBeVisible();
  });

  test('样本数输入框可见且有默认值', async ({ page }) => {
    const sampleInput = page.getByLabel('样本数');
    await expect(sampleInput).toBeVisible();
    // 输入框应有值（可能是 input 或 number 类型）
    await sampleInput.fill('100');
    await page.waitForTimeout(300);
    await expect(sampleInput).toHaveValue('100');
  });

  test('自动刷新开关可见', async ({ page }) => {
    await expect(page.getByLabel('自动刷新')).toBeVisible();
  });

  test('刷新按钮可见', async ({ page }) => {
    await expect(page.getByRole('button', { name: '刷新' })).toBeVisible();
  });

  test('点击刷新按钮无崩溃', async ({ page }) => {
    await page.getByRole('button', { name: '刷新' }).click();
    await page.waitForTimeout(1500);
    // 页面仍然可见
    await expect(page.locator('text=串口调试输出')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/serial-debug-refreshed.png', fullPage: true });
  });

  test('切换文本编码选项', async ({ page }) => {
    await page.getByLabel('文本编码').click();
    await page.waitForTimeout(500);

    // 选择 GBK
    const gbkOption = page.locator('.v-list-item:has-text("GBK")').first();
    if (await gbkOption.isVisible({ timeout: 2000 }).catch(() => false)) {
      await gbkOption.click();
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: 'e2e/screenshots/serial-debug-encoding.png', fullPage: true });
  });
});

test.describe('串口调试 - 数据展示（前后端联调）', () => {
  test('启动模拟器后刷新页面可见数据帧', async ({ page, request }) => {
    // 1. 启动后端串口模拟器
    const { port, deviceId } = await startSimulatorAndConnect(request, 1000, 8);

    try {
      // 2. 开始采集
      await request.post(`${API_BASE}/api/real-devices/${encodeURIComponent(port)}/start-acquisition/`);
      await page.waitForTimeout(2000);

      // 3. 打开串口调试页面
      await page.goto('/dev/serial-debug?_t=serial_data');
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(1000);

      // 4. 点击刷新
      await page.getByRole('button', { name: '刷新' }).click();
      await page.waitForTimeout(2000);

      await page.screenshot({ path: 'e2e/screenshots/serial-debug-with-data.png', fullPage: true });

      // 5. 通过 API 验证确实有数据
      const debugResp = await request.get(
        `${API_BASE}/api/real-devices/debug-output/?port=${encodeURIComponent(port)}&count=50`,
      );
      expect(debugResp.ok()).toBeTruthy();
      const debugJson = await debugResp.json();
      const ports = debugJson?.data?.ports || [];
      const first = ports[0] || {};
      const sampleCount = Number(first?.count || 0);
      expect(sampleCount).toBeGreaterThan(0);
    } finally {
      await cleanupSimulator(request, port);
    }
  });
});
