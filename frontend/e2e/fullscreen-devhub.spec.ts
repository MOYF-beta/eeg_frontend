/**
 * 全屏视图与开发目录 E2E 测试
 *
 * 覆盖：
 *   - FullscreenView (/fullscreen/:type/:nodeId)
 *   - DevHubView (/dev) 导航
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) 运行中。
 */
import { test, expect } from '@playwright/test';
import { teardownGraph, buildMinimalGraph, sendControlCmd, sendControlCmdSafe } from './helpers';

test.describe('开发目录页面', () => {
  test('页面加载显示标题与导航链接', async ({ page }) => {
    await page.goto('/dev?_t=devhub');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    // 开发目录标题
    await expect(page.locator('text=开发目录').or(page.locator('text=DevHub'))).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/devhub-basic.png', fullPage: true });
  });

  test('包含设备管理导航链接', async ({ page }) => {
    await page.goto('/dev?_t=devhub_nav');
    await page.waitForLoadState('networkidle');

    const deviceLink = page.locator('a:has-text("设备管理"), .v-list-item:has-text("设备管理")').first();
    if (await deviceLink.isVisible({ timeout: 2000 }).catch(() => false)) {
      await deviceLink.click();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/devices/);
    }
  });

  test('包含串口调试导航链接', async ({ page }) => {
    await page.goto('/dev?_t=devhub_nav2');
    await page.waitForLoadState('networkidle');

    const serialLink = page.locator('a:has-text("串口调试"), .v-list-item:has-text("串口调试")').first();
    if (await serialLink.isVisible({ timeout: 2000 }).catch(() => false)) {
      await serialLink.click();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/serial-debug/);
    }
  });
});

test.describe('全屏视图', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page);
  });

  test('全屏示波器路由加载不崩溃', async ({ page }) => {
    // 先准备一张运行中的图
    await page.goto('/cpgraph?_t=fullscreen_setup');
    await page.waitForLoadState('networkidle');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });
    await sendControlCmd(page, 'run', { mode: 'live' });

    // 打开全屏示波器页面（使用 E2E 示波器的 nodeId）
    await page.goto('/fullscreen/osc/e2e-output-1?_t=fullscreen_osc');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 页面应加载（不崩溃）
    await expect(page.locator('body')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/fullscreen-osc.png', fullPage: true });

    // 清理
    await sendControlCmdSafe(page, 'stop');
  });

  test('全屏频谱路由加载不崩溃', async ({ page }) => {
    await page.goto('/cpgraph?_t=fullscreen_setup2');
    await page.waitForLoadState('networkidle');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });
    await sendControlCmd(page, 'run', { mode: 'live' });

    await page.goto('/fullscreen/freq/e2e-output-1?_t=fullscreen_freq');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await expect(page.locator('body')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/fullscreen-freq.png', fullPage: true });

    await sendControlCmdSafe(page, 'stop');
  });

  test('全屏视图添加 is-fullscreen-view body class', async ({ page }) => {
    await page.goto('/fullscreen/osc/e2e-output-1?_t=fullscreen_class');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // body 应有 is-fullscreen-view class（用于隐藏导航栏）
    const bodyClass = await page.locator('body').getAttribute('class');
    expect(bodyClass || '').toContain('is-fullscreen-view');
  });
});
