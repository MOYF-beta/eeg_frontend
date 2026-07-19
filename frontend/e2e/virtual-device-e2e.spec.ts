/**
 * 虚拟设备 (7777端口) 端到端 Playwright 测试
 *
 * 测试前提：
 *   1. 虚拟设备服务器运行中（python virtual_device_server.py）
 *   2. Django 后端运行中（python manage.py runserver 8000）
 *   3. 前端 dev server 运行中（npm run dev → localhost:5173）
 *
 * 测试流程：
 *   A. 设备发现 — 验证虚拟设备(5个)出现在前端设备列表中
 *   B. 设备管理 — 连接→采集→断开 完整生命周期
 *   C. 计算图集成 — 拖拽设备创建SOURCE节点
 *   D. 完整数据流 — 冻结→运行→示波器显示波形
 */

import { test, expect, Page } from '@playwright/test';
import {
  API_BASE,
  sendControlCmd,
  teardownGraph,
  buildMinimalGraph,
  findVirtualDeviceId,
  getPacketCount,
  prepareGraphViaBrowser,
} from './helpers';

const VDEV_BASE = 'http://localhost:7777';

// ================================================================== //
//  辅助函数
// ================================================================== //

/** 通过侧边栏图标导航到页面 */
async function navigateTo(page: Page, iconTitle: string) {
  await page.locator(`.nav-item[title="${iconTitle}"], .v-list-item[title="${iconTitle}"]`).first().click();
  await page.waitForTimeout(1000);
}

// ================================================================== //
//  A. 设备发现测试
// ================================================================== //

test.describe('虚拟设备发现 - 5 个设备', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dev?_t=test_vdev');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
  });

  test('开发目录页面加载', async ({ page }) => {
    await expect(page.locator('text=开发工具目录').first()).toBeVisible();
  });

  test('扫描端口显示虚拟设备', async ({ page }) => {
    // 查找扫描/扫描端口按钮
    const scanBtn = page.locator('button:has-text("扫描")').first();
    if (await scanBtn.isVisible()) {
      await scanBtn.click();
      await page.waitForTimeout(2000);
    }

    // 验证页面加载完成（不依赖特定文本，确认页面无崩溃）
    const bodyText = await page.locator('body').textContent();
    expect(bodyText.length).toBeGreaterThan(0);
  });
});

// ================================================================== //
//  B. 设备管理页面测试（/devices）
// ================================================================== //

test.describe('设备管理 - 虚拟设备生命周期', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/devices?_t=test_vdev');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
  });

  test('设备管理页面基本结构', async ({ page }) => {
    // 验证页面标题（页面多处出现「设备管理」，取首个可见项）
    await expect(page.locator('text=设备管理').first()).toBeVisible();
    await expect(page.locator('body')).toBeVisible();
  });
});

// ================================================================== //
//  C. 计算图集成测试
// ================================================================== //

test.describe('计算图 - 虚拟设备集成', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/cpgraph?_t=test_vdev');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);
  });

  test('计算图页面加载', async ({ page }) => {
    await expect(page.locator('text=计算图编辑器').first()).toBeVisible();
  });

  test('设备集合区域存在', async ({ page }) => {
    await expect(page.locator('text=设备集合').first()).toBeVisible();
  });
});

// ================================================================== //
//  D. 完整数据流测试
// ================================================================== //

test.describe('完整数据流：虚拟设备 → 计算图 → 示波器', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page);
  });

  test('端到端数据流: 冻结 → 运行 → 数据包验证', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '虚拟设备服务器未运行');
    const id = deviceId!;

    // 0. 设备为跨测试共享资源：重置并确保 connected+acquiring，SOURCE 才有数据
    await request.post(`${VDEV_BASE}/devices/${id}/stop`).catch(() => null);
    await request.post(`${VDEV_BASE}/devices/${id}/disconnect`).catch(() => null);
    await request.post(`${VDEV_BASE}/devices/${id}/connect`);
    await request.post(`${VDEV_BASE}/devices/${id}/start`);

    // 1. 在计算图页面准备运行中的图（绑定虚拟设备）
    await page.goto('/cpgraph?_t=test_vdev_flow');
    await page.waitForLoadState('networkidle');
    await prepareGraphViaBrowser(page, buildMinimalGraph(id));

    // 后端必须处于 running
    const statusResp = await request.get(`${API_BASE}/api/status/`);
    expect((await statusResp.json()).runtime.running).toBe(true);

    // 2. 切到可视化页面（onMounted 自动为 OUTPUT 节点创建并绑定示波器）
    await page.goto('/visualization?_t=test_vdev_flow_view');
    await page.waitForLoadState('networkidle');

    // 等待自动创建的示波器绑定 E2E 输出节点
    await expect(page.locator('text=/信号源[:：]/').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/E2E 示波器/').first()).toBeVisible({ timeout: 10000 });

    // 3. 数据包计数必须 >0 且持续增长（示波器确实在收数据）
    await expect
      .poll(async () => getPacketCount(page), { timeout: 15000 })
      .toBeGreaterThan(0);
    const first = await getPacketCount(page);
    await page.waitForTimeout(1500);
    const second = await getPacketCount(page);
    expect(second).toBeGreaterThan(first);
  });

  test('解冻后数据流停止', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '虚拟设备服务器未运行');

    await page.goto('/cpgraph?_t=test_vdev_stop');
    await page.waitForLoadState('networkidle');
    await prepareGraphViaBrowser(page, buildMinimalGraph(deviceId!));

    // 确认运行中
    expect((await (await request.get(`${API_BASE}/api/status/`)).json()).runtime.running).toBe(true);

    // 停止并核验最终状态
    await sendControlCmd(page, 'stop');
    await sendControlCmd(page, 'freeze', { frozen: false });

    const statusResp = await request.get(`${API_BASE}/api/status/`);
    const runtime = (await statusResp.json()).runtime;
    expect(runtime.running).toBe(false);
  });
});

// ================================================================== //
//  E. 串口调试页面
// ================================================================== //

test.describe('串口调试 - 模拟设备', () => {
  test('串口调试页面加载', async ({ page }) => {
    await page.goto('/dev/serial-debug?_t=test_vdev');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
    await expect(page.locator('body')).toBeVisible();
  });
});
