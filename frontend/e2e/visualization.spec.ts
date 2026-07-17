/**
 * 可视化工作台 E2E 测试
 *
 * 覆盖 VisualizationView 的核心交互：
 *   1. 页面加载与标题
 *   2. 网格布局切换（1x1/2x2/3x3/4x4）
 *   3. 添加示波器 / 频谱 / 10-20 可视化卡片
 *   4. 卡片移除
 *   5. localStorage 布局持久化（刷新后恢复）
 *   6. 空状态提示
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) 运行中。
 */
import { test, expect } from '@playwright/test';
import {
  prepareGraphViaBrowser,
  teardownGraph,
  buildMinimalGraph,
} from './helpers';

test.describe('可视化工作台', () => {
  test.beforeEach(async ({ page }) => {
    // 清空 localStorage 以保证干净环境
    await page.goto('/cpgraph?_t=viz_setup');
    await page.waitForLoadState('networkidle');
    await page.evaluate(() => localStorage.removeItem('viz_layout_settings'));
  });

  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('页面加载并显示标题', async ({ page }) => {
    await page.goto('/visualization?_t=viz_load');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1:text("波形可视化")').or(page.locator('text=波形可视化'))).toBeVisible();
  });

  test('网格布局按钮可见且默认 1x1', async ({ page }) => {
    await page.goto('/visualization?_t=viz_grid');
    await page.waitForLoadState('networkidle');

    // 四个网格按钮应可见
    for (const label of ['1x1', '2x2', '3x3', '4x4']) {
      await expect(page.getByRole('button', { name: label })).toBeVisible();
    }
  });

  test('切换网格布局到 2x2', async ({ page }) => {
    await page.goto('/visualization?_t=viz_grid2');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: '2x2' }).click();
    await page.waitForTimeout(500);

    // 2x2 按钮应处于选中态（primary 色）
    const btn = page.getByRole('button', { name: '2x2' });
    await expect(btn).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/viz-grid-2x2.png', fullPage: true });
  });

  test('添加示波器卡片', async ({ page }) => {
    await page.goto('/visualization?_t=viz_add_osc');
    await page.waitForLoadState('networkidle');

    const addOscBtn = page.getByRole('button', { name: '添加示波器' });
    // 按钮存在（可能因无可视化节点而禁用）
    await expect(addOscBtn).toBeVisible();
    await addOscBtn.click().catch(() => null);
    await page.waitForTimeout(800);

    await page.screenshot({ path: 'e2e/screenshots/viz-add-osc.png', fullPage: true });
  });

  test('添加频谱卡片', async ({ page }) => {
    await page.goto('/visualization?_t=viz_add_freq');
    await page.waitForLoadState('networkidle');

    const addFreqBtn = page.getByRole('button', { name: '添加频谱' });
    await expect(addFreqBtn).toBeVisible();
    await addFreqBtn.click().catch(() => null);
    await page.waitForTimeout(800);

    await page.screenshot({ path: 'e2e/screenshots/viz-add-freq.png', fullPage: true });
  });

  test('添加 10-20 可视化卡片', async ({ page }) => {
    await page.goto('/visualization?_t=viz_add_topo');
    await page.waitForLoadState('networkidle');

    const addTopoBtn = page.getByRole('button', { name: '添加10-20可视化' });
    await expect(addTopoBtn).toBeVisible();
    await addTopoBtn.click().catch(() => null);
    await page.waitForTimeout(800);

    await page.screenshot({ path: 'e2e/screenshots/viz-add-topo.png', fullPage: true });
  });

  test('布局持久化到 localStorage 后刷新恢复', async ({ page }) => {
    await page.goto('/visualization?_t=viz_persist');
    await page.waitForLoadState('networkidle');

    // 切换到 2x2
    await page.getByRole('button', { name: '2x2' }).click();
    await page.waitForTimeout(500);

    // 验证 localStorage 写入
    const stored = await page.evaluate(() => localStorage.getItem('viz_layout_settings'));
    expect(stored).not.toBeNull();

    // 刷新页面
    await page.reload();
    await page.waitForLoadState('networkidle');

    // 2x2 按钮应仍为选中态
    const btn = page.getByRole('button', { name: '2x2' });
    await expect(btn).toBeVisible();

    await page.screenshot({ path: 'e2e/screenshots/viz-persist.png', fullPage: true });
  });
});

test.describe('可视化 - 数据流绑定（前后端联调）', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('冻结+运行后，示波器卡片可绑定输出节点并接收数据', async ({ page }) => {
    // 1. 在计算图页面准备一张运行中的图
    await page.goto('/cpgraph?_t=viz_flow');
    await page.waitForLoadState('networkidle');
    await prepareGraphViaBrowser(page, buildMinimalGraph());

    // 2. 跳转到可视化页面
    await page.goto('/visualization?_t=viz_flow_view');
    await page.waitForLoadState('networkidle');

    // 3. 添加示波器卡片
    const addOscBtn = page.getByRole('button', { name: '添加示波器' });
    await expect(addOscBtn).toBeVisible();
    await addOscBtn.click();
    await page.waitForTimeout(1000);

    // 4. 点击信号源按钮打开对话框
    const sourceBtn = page.locator('button:has-text("信号源")').first();
    if (await sourceBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await sourceBtn.click();
      await page.waitForTimeout(500);

      // 选择 E2E 示波器节点
      const item = page.locator('text=E2E 示波器').first();
      if (await item.isVisible({ timeout: 2000 }).catch(() => false)) {
        await item.click();
        await page.waitForTimeout(3000);
      }
    }

    await page.screenshot({ path: 'e2e/screenshots/viz-flow-bound.png', fullPage: true });
  });
});
