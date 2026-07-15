import { test, expect } from '@playwright/test';

test.describe('计算图主导工作台', () => {
  test('设备集合拖拽与节点固定面板预览', async ({ page }) => {
    await page.goto('/cpgraph?_t=graph-led');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=设备集合')).toBeVisible();

    await page.click('button:has-text("新建设备")');
    const dialogInputs = page.locator('.v-dialog input');
    await dialogInputs.first().fill('图编辑器新设备');
    await page.click('button:has-text("创建并加入设备集合")');

    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'e2e/screenshots/10-graph-led-device-set.png', fullPage: true });

    // 从后端加载计算图
    await page.waitForTimeout(1200);

    await page.click('button[title="固定到悬浮面板"]');

    await expect(page.locator('text=节点固定面板')).toBeVisible();
    await page.click('[role="tab"]:has-text("预览")');
    await page.waitForTimeout(800);

    await page.screenshot({ path: 'e2e/screenshots/11-pinned-node-preview.png', fullPage: true });
  });
});
