import { test, expect } from '@playwright/test';

test.describe('侧边栏折叠态运行控制', () => {
  test('折叠后仍显示Live/停止按钮并截图', async ({ page }) => {
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const toggleBtn = page.getByTestId('sidebar-toggle-btn');
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();
    await page.waitForTimeout(300);

    const railControls = page.getByTestId('sidebar-rail-controls');
    const liveBtn = page.getByTestId('sidebar-live-run-btn');
    const stopBtn = page.getByTestId('sidebar-stop-run-btn');

    await expect(railControls).toBeVisible();
    await expect(liveBtn).toBeVisible();
    await expect(stopBtn).toBeVisible();

    await page.screenshot({
      path: 'e2e/screenshots/sidebar-collapsed-controls.png',
      fullPage: true,
    });
  });
});
