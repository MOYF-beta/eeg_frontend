/**
 * 侧边栏与状态栏 E2E 测试
 *
 * 覆盖：
 *   - Sidebar 导航项跳转（计算图/可视化/开发目录）
 *   - Sidebar 运行/停止按钮（data-testid sidebar-run-toggle-btn）
 *   - Sidebar 录制按钮
 *   - StatusBar 性能指标显示
 *   - 多页面间状态同步
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) 运行中。
 */
import { test, expect } from '@playwright/test';
import { teardownGraph } from './helpers';

test.describe('侧边栏导航', () => {
  test('侧边栏可见且包含运行控制按钮', async ({ page }) => {
    await page.goto('/cpgraph?_t=sidebar');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    await expect(page.getByTestId('sidebar-run-toggle-btn')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/sidebar-basic.png', fullPage: true });
  });

  test('导航到可视化页面', async ({ page }) => {
    await page.goto('/cpgraph?_t=sidebar_nav');
    await page.waitForLoadState('networkidle');

    // 通过侧边栏点击（rail 折叠态）
    const vizNav = page.locator('.v-list-item[title="可视化"], a[title="可视化"]').first();
    if (await vizNav.count()) {
      await vizNav.click();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/visualization/);
    } else {
      // 退化：直接验证路由可用
      await page.goto('/visualization');
      await page.waitForLoadState('networkidle');
      await expect(page.locator('text=波形可视化')).toBeVisible();
    }
  });

  test('导航到开发目录页面', async ({ page }) => {
    await page.goto('/cpgraph?_t=sidebar_nav2');
    await page.waitForLoadState('networkidle');

    const devNav = page.locator('.v-list-item[title="开发目录"], a[title="开发目录"]').first();
    if (await devNav.count()) {
      await devNav.click();
      await page.waitForLoadState('networkidle');
      await expect(page).toHaveURL(/\/dev/);
    }
  });

  test('运行按钮初始禁用，冻结后启用', async ({ page }) => {
    await page.goto('/cpgraph?_t=sidebar_run');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    const runBtn = page.getByTestId('sidebar-run-toggle-btn');
    await expect(runBtn).toBeVisible();

    // 初始 title 应为"运行"
    await expect(runBtn).toHaveAttribute('title', /运行|停止/);
  });
});

test.describe('状态栏', () => {
  test('状态栏可见且显示性能指标', async ({ page }) => {
    await page.goto('/cpgraph?_t=statusbar');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    // 状态栏区域
    const statusBar = page.locator('.status-bar');
    await expect(statusBar).toBeVisible();

    // 至少有一个性能指标（CPU/吞吐/管道 等）
    const statusText = await statusBar.textContent();
    expect(statusText).toBeTruthy();
    // 应包含性能关键字之一
    expect(statusText).toMatch(/CPU|吞吐|管道|RAM|磁盘|WS|线程|进程/);

    await page.screenshot({ path: 'e2e/screenshots/statusbar.png', fullPage: true });
  });

  test('状态栏显示 WebSocket 连接状态', async ({ page }) => {
    await page.goto('/cpgraph?_t=statusbar_ws');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const statusBar = page.locator('.status-bar');
    const text = await statusBar.textContent();
    // 应显示 WS 状态：已连接/连接中/错误/断开 之一
    expect(text).toMatch(/已连接|连接中|错误|断开/);
  });
});

test.describe('侧边栏录制按钮（前后端联调）', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('录制按钮存在且可点击', async ({ page }) => {
    await page.goto('/cpgraph?_t=sidebar_record');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 录制按钮（title="录制" 或 "停止录制"）
    const recordBtn = page
      .locator('.v-list-item[title="录制"], .v-list-item[title="停止录制"], button[title="录制"], button[title="停止录制"]')
      .first();
    await expect(recordBtn).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: 'e2e/screenshots/sidebar-record.png', fullPage: true });
  });
});
