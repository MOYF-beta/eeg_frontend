import { test, expect } from '@playwright/test';

test.describe('侧边栏折叠态运行控制', () => {
  test('侧边栏默认折叠，显示运行/停止按钮并截图', async ({ page }) => {
    await page.goto('/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const runBtn = page.getByTestId('sidebar-run-toggle-btn');
    await expect(runBtn).toBeVisible();

    await page.screenshot({
      path: 'e2e/screenshots/sidebar-collapsed-controls.png',
      fullPage: true,
    });
  });
});
