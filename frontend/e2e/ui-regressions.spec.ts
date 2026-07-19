/**
 * UI 回归 E2E 测试（覆盖 2026-07-19 修复的 UI 缺陷）
 *
 * 覆盖：
 *   1. 节点面板可滚动（palette-body min-height:0 修复）
 *   2. 设备分组折叠后不会因轮询重新展开
 *   3. 运行时隐藏「编辑中」chip
 *   4. 示波器在未运行时不显示「计算图未冻结」
 *   5. 录制按钮未运行时点击可自动启动运行并录制；状态栏显示录制指示
 *   6. 节点长名称在节点边界内截断（不溢出）
 *   7. 浅色/深色主题下节点文字颜色正确
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) + 虚拟设备服务器运行中。
 */
import { test, expect } from '@playwright/test';
import {
  API_BASE,
  buildMinimalGraph,
  prepareGraphViaBrowser,
  teardownGraph,
  findVirtualDeviceId,
  waitForGraphEditor,
} from './helpers';

test.describe('节点面板', () => {
  test('节点面板内容超高时可滚动', async ({ page }) => {
    await page.goto('/cpgraph?_t=ui_palette');
    await waitForGraphEditor(page);
    await page.waitForTimeout(800);

    const paletteBody = page.locator('.palette-body');
    await expect(paletteBody).toBeVisible();

    // 展开全部分组后内容高度应超过可视高度，且 scrollTop 可改变
    const scrollable = await paletteBody.evaluate((el) => {
      const canScroll = el.scrollHeight > el.clientHeight;
      if (!canScroll) return { canScroll, moved: false };
      el.scrollTop = el.scrollHeight;
      return { canScroll, moved: el.scrollTop > 0 };
    });
    expect(scrollable.canScroll).toBe(true);
    expect(scrollable.moved).toBe(true);
  });
});

test.describe('设备分组折叠', () => {
  test('折叠驱动分组后保持折叠状态', async ({ page }) => {
    await page.goto('/devices?_t=ui_collapse');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    const panelTitle = page.locator('.v-expansion-panel-title').first();
    await expect(panelTitle).toBeVisible();

    // 初始应为展开（aria-expanded=true），点击折叠
    if ((await panelTitle.getAttribute('aria-expanded')) === 'true') {
      await panelTitle.click();
      await page.waitForTimeout(400);
    }
    await expect(panelTitle).toHaveAttribute('aria-expanded', 'false');

    // 等待设备轮询刷新（>2s），折叠状态不得恢复
    await page.waitForTimeout(2500);
    await expect(panelTitle).toHaveAttribute('aria-expanded', 'false');
  });
});

test.describe('运行状态显示', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('运行时不显示「编辑中」', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '无可用虚拟设备');

    await page.goto('/cpgraph?_t=ui_editing');
    await waitForGraphEditor(page);

    await prepareGraphViaBrowser(page, buildMinimalGraph(deviceId!) as any);
    await page.waitForTimeout(1500);

    // 应显示「运行中」，且不存在「编辑中」chip
    await expect(page.locator('.graph-toolbar').getByText('运行中')).toBeVisible();
    await expect(page.locator('.graph-toolbar').getByText('编辑中')).toHaveCount(0);
  });

  test('示波器在未运行时不显示「计算图未冻结」', async ({ page }) => {
    await page.goto('/visualization?_t=ui_frozen');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    await expect(page.getByText('计算图未冻结')).toHaveCount(0);
  });
});

test.describe('录制流程', () => {
  test.afterEach(async ({ page, request }) => {
    await request.delete(`${API_BASE}/api/graph/record/`).catch(() => null);
    await teardownGraph(page).catch(() => null);
  });

  test('未运行时点击录制按钮自动启动运行并录制，状态栏显示录制指示', async ({
    page,
    request,
  }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '无可用虚拟设备');

    await page.goto('/cpgraph?_t=ui_record');
    await waitForGraphEditor(page);

    // 构建含录制开关的图（saveEnabled=true，后端才会纳入录制）
    const graph = buildMinimalGraph(deviceId!) as any;
    graph.nodes[1].params.saveEnabled = true;
    graph.nodes[1].params.filename = 'e2e_ui_record_test.csv';

    // 同步图但不运行
    const { sendControlCmd } = await import('./helpers');
    await sendControlCmd(page, 'stop').catch(() => null);
    const sync = await sendControlCmd(page, 'sync_graph', { graph });
    expect(sync.ok).toBeTruthy();
    await page.waitForTimeout(800);

    // 点击侧边栏录制按钮（等待启用：未运行时需 canRunGraph=true）
    const recordBtn = page.getByTestId('sidebar-record-btn');
    await expect(recordBtn).toBeVisible();
    await expect(recordBtn).toBeEnabled({ timeout: 10000 });
    await recordBtn.click();

    // 录制状态应出现：状态栏出现录制指示并显示文件名
    const recIndicator = page.getByTestId('statusbar-recording');
    await expect(recIndicator).toBeVisible({ timeout: 15000 });
    await expect(recIndicator).toContainText('e2e_ui_record_test.csv');

    // 停止录制（再次点击录制按钮）
    await expect(recordBtn).toBeEnabled({ timeout: 10000 });
    await recordBtn.click();
    await expect(recIndicator).toHaveCount(0, { timeout: 10000 });
  });
});

test.describe('节点显示', () => {
  test('长节点名称在节点边界内截断不溢出', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '无可用虚拟设备');

    await page.goto('/cpgraph?_t=ui_overflow');
    await waitForGraphEditor(page);

    const graph = buildMinimalGraph(deviceId!) as any;
    graph.nodes[0].name = '这是一个非常非常长的节点名称 Alpha 波模拟器 simulated:sim_alpha';

    const { sendControlCmd } = await import('./helpers');
    await sendControlCmd(page, 'stop').catch(() => null);
    const sync = await sendControlCmd(page, 'sync_graph', { graph });
    expect(sync.ok).toBeTruthy();
    await page.waitForTimeout(1500);

    // 节点 label 文本应被截断（含省略号），不超过节点宽度
    const overflow = await page.evaluate(() => {
      const svgTexts = Array.from(document.querySelectorAll('.x6-node text'));
      const results: { ok: boolean; text: string }[] = [];
      for (const t of svgTexts) {
        const node = t.closest('.x6-node');
        const body = node?.querySelector('rect');
        if (!body) continue;
        const bodyWidth = Number(body.getAttribute('width') || 0);
        const bbox = (t as SVGGraphicsElement).getBBox();
        results.push({
          ok: bbox.width <= bodyWidth + 2,
          text: (t.textContent || '').slice(0, 30),
        });
      }
      return results;
    });
    expect(overflow.length).toBeGreaterThan(0);
    for (const item of overflow) {
      expect(item.ok, `文本「${item.text}」超出节点边界`).toBe(true);
    }
  });

  test('浅色/深色主题下节点文字颜色正确', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '无可用虚拟设备');

    await page.goto('/cpgraph?_t=ui_theme');
    await waitForGraphEditor(page);

    const { sendControlCmd } = await import('./helpers');
    await sendControlCmd(page, 'stop').catch(() => null);
    const sync = await sendControlCmd(page, 'sync_graph', {
      graph: buildMinimalGraph(deviceId!),
    });
    expect(sync.ok).toBeTruthy();
    await page.waitForTimeout(1200);

    const getLabelFill = () =>
      page.evaluate(() => {
        // 找到含节点名称文本的 label（排除 badgeText 图标文本）
        const texts = Array.from(document.querySelectorAll('.x6-node text'));
        const label = texts.find((t) => (t.textContent || '').includes('E2E'));
        return label ? label.getAttribute('fill') : null;
      });

    // 当前主题（默认跟随系统；显式切换两次验证）
    const themeBtn = page.getByTestId('sidebar-theme-toggle-btn');
    await expect(themeBtn).toBeVisible();

    const fillBefore = await getLabelFill();
    await themeBtn.click();
    await page.waitForTimeout(600);
    const fillAfter = await getLabelFill();

    expect(fillBefore).toBeTruthy();
    expect(fillAfter).toBeTruthy();
    // 切换主题后节点文字颜色必须变化（深色 #E4E9F4 ↔ 浅色 #333333）
    expect(fillBefore).not.toEqual(fillAfter);

    // 切回原主题
    await themeBtn.click();
    await page.waitForTimeout(600);
    expect(await getLabelFill()).toEqual(fillBefore);
  });
});
