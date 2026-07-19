/**
 * 设备管理页面 E2E 测试
 *
 * 覆盖：
 *   1. 页面加载与基本结构（设备管理标题、刷新按钮、设备卡片、连接状态徽标）
 *   2. 刷新交互
 *   3. 设备管理 API 联调（列表 / 状态 / 端口扫描）
 *   4. 设备 CRUD（前后端联调）
 *
 * 说明：当前设备管理页 UI 已重构为「设备管理」+ 已加载驱动 + 虚拟设备驱动卡片布局，
 * 不再有独立的「真实设备管理 / 设备列表 / 一键扫描 / 添加设备」区块，选择器据此更新。
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000) 运行中。
 */
import { test, expect } from '@playwright/test';
import { API_BASE, teardownGraph } from './helpers';

test.describe('设备管理页面', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/devices?_t=devmgmt');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('页面加载显示设备管理标题与设备计数', async ({ page }) => {
    // 页面有且仅有一个「设备管理」标题（后接「N 台设备」统计）
    await expect(page.locator('text=设备管理').first()).toBeVisible();
    await expect(page.locator('text=/\\d+ 台设备/')).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/devmgmt-basic.png', fullPage: true });
  });

  test('已加载驱动与虚拟设备驱动区块可见', async ({ page }) => {
    await expect(page.locator('text=/已加载驱动/')).toBeVisible();
    await expect(page.locator('text=/虚拟设备驱动/')).toBeVisible();
  });

  test('设备卡片与连接状态徽标可见，刷新按钮可用', async ({ page }) => {
    // 至少一张设备卡片（模拟器设备）
    await expect(page.locator('text=/模拟器|sim_/').first()).toBeVisible();
    // 至少一个连接状态徽标（已连接 / 未连接）
    await expect(page.locator('text=/已连接|未连接/').first()).toBeVisible();
    // 刷新按钮
    await expect(page.getByRole('button', { name: '刷新' }).first()).toBeVisible();
  });

  test('点击刷新按钮刷新设备列表且无崩溃', async ({ page }) => {
    const refreshBtn = page.getByRole('button', { name: '刷新' }).first();
    await expect(refreshBtn).toBeEnabled();
    await refreshBtn.click();
    await page.waitForTimeout(1500);
    // 刷新后设备管理标题仍在（页面未崩溃）
    await expect(page.locator('text=设备管理').first()).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/devmgmt-refreshed.png', fullPage: true });
  });
});

test.describe('设备管理 - API 联调', () => {
  test('通过 API 获取设备列表并验证结构', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
    // data 为 { devices: [...] }，验证设备条目字段结构
    const devices = Array.isArray(body.data) ? body.data : body.data.devices;
    expect(Array.isArray(devices)).toBe(true);
    expect(devices.length).toBeGreaterThan(0);
    for (const d of devices) {
      expect(d).toHaveProperty('device_id');
      expect(d).toHaveProperty('status');
    }
  });

  test('通过 API 获取设备状态', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/status/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });

  test('通过 API 扫描端口', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/scan-ports/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
    // data 为 { ports: [...] }，验证端口条目字段
    const ports = Array.isArray(body.data) ? body.data : body.data.ports;
    expect(Array.isArray(ports)).toBe(true);
    expect(ports.length).toBeGreaterThan(0);
    for (const p of ports) {
      expect(p).toHaveProperty('port');
      expect(p).toHaveProperty('driver_type');
    }
  });
});

test.describe('设备 CRUD（前后端联调）', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test('创建设备返回 201 及设备配置', async ({ page, request }) => {
    // 后端 _create_device 仅记录用户自定义配置（设备实际由驱动发现），
    // 返回确认不持久化，因此验收契约 = 201 + 反映请求参数的 data。
    const createResp = await request.post(`${API_BASE}/api/real-devices/`, {
      data: {
        id: 'e2e-test-device',
        name: 'E2E 测试设备',
        type: 'simulated',
        sampling_rate: 500,
        channel_count: 4,
        address: 'e2e-test',
      },
    });
    expect(createResp.status()).toBe(201);
    const body = await createResp.json();
    expect(body.ok).toBe(true);
    expect(body.data.name).toBe('E2E 测试设备');
    expect(body.data.type).toBe('simulated');
    expect(body.data.sampling_rate).toBe(500);
    expect(body.data.channel_count).toBe(4);
    expect(body.data.status).toBe('ready');
  });

  test('重复创建相同设备幂等', async ({ request }) => {
    // 创建不持久化，重复创建同一配置应幂等返回 201
    const payload = {
      name: 'E2E 幂等设备',
      type: 'simulated',
      sampling_rate: 250,
      channel_count: 8,
      address: 'e2e-idem',
    };
    const r1 = await request.post(`${API_BASE}/api/real-devices/`, { data: payload });
    const r2 = await request.post(`${API_BASE}/api/real-devices/`, { data: payload });
    expect(r1.status()).toBe(201);
    expect(r2.status()).toBe(201);
    const b1 = await r1.json();
    const b2 = await r2.json();
    expect(b1.data.id).toBe(b2.data.id);
  });

  test('运行时可更新已发现设备配置', async ({ page, request }) => {
    // 先通过 WS 运行图
    await page.goto('/cpgraph?_t=devmgmt_runtime');
    await page.waitForLoadState('networkidle');
    const { prepareGraphViaBrowser, buildMinimalGraph } = await import('./helpers');
    await prepareGraphViaBrowser(page, buildMinimalGraph());

    // 确认处于 running 状态
    const statusResp = await request.get(`${API_BASE}/api/status/`);
    expect((await statusResp.json()).runtime.running).toBe(true);

    // 后端 _update_device 不限制运行态，对已发现设备 PATCH 应成功。
    // 先取一个真实已发现设备 id。
    const listResp = await request.get(`${API_BASE}/api/real-devices/`);
    const listBody = await listResp.json();
    const devices = Array.isArray(listBody.data) ? listBody.data : listBody.data?.devices || [];
    expect(devices.length).toBeGreaterThan(0);
    const targetId = devices[0].id || devices[0].device_id;

    const patchResp = await request.patch(
      `${API_BASE}/api/real-devices/${encodeURIComponent(targetId)}/`,
      { data: { name: '运行时更新名称' } },
    );
    expect(patchResp.ok()).toBeTruthy();
    const patchBody = await patchResp.json();
    expect(patchBody.ok).toBe(true);
    expect(patchBody.data.name).toBe('运行时更新名称');
  });
});
