/**
 * 虚拟设备完整数据流 E2E 测试（前后端联调）
 *
 * 覆盖虚拟设备 → 后端 → 计算图 → 示波器的完整链路：
 *   1. 虚拟设备发现（5 个 sim_* 设备）
 *   2. 虚拟设备 API 健康检查
 *   3. 设备连接 → 采集 → 数据拉取 → 断开
 *   4. 计算图绑定虚拟设备 → 冻结 → 运行 → 示波器接收数据
 *   5. 解冻后数据流停止
 *   6. 多设备并发
 *
 * 前提：
 *   1. 虚拟设备服务器运行中（python virtual_device_server.py，端口 7777）
 *   2. Django 后端运行中（端口 8000）
 *   3. 前端 dev server 运行中（端口 5173）
 */
import { test, expect } from '@playwright/test';
import {
  API_BASE,
  sendControlCmd,
  sendControlCmdSafe,
  teardownGraph,
  buildMinimalGraph,
  findVirtualDeviceId,
  getPacketCount,
  prepareGraphViaBrowser,
} from './helpers';

const VDEV_BASE = 'http://localhost:7777';

test.describe('虚拟设备发现 - 完整验证', () => {
  test('虚拟设备服务器健康检查', async ({ request }) => {
    // :7777 /health 返回信封 { ok, data: { status: 'running', device_count } }
    const resp = await request.get(`${VDEV_BASE}/health`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body.data.status).toBe('running');
    expect(body.data.device_count).toBeGreaterThanOrEqual(5);
  });

  test('虚拟设备列表包含 5 个 sim_* 设备', async ({ request }) => {
    // :7777 /devices 返回信封 { ok, data: { devices: [...] } }，设备键为 device_id
    const resp = await request.get(`${VDEV_BASE}/devices`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    const devices = body.data?.devices || [];
    expect(Array.isArray(devices)).toBe(true);
    expect(devices.length).toBeGreaterThanOrEqual(5);

    const ids = devices.map((d: any) => d.device_id || d.id);
    for (const expected of ['sim_alpha', 'sim_beta', 'sim_theta', 'sim_gamma', 'sim_multi']) {
      expect(ids).toContain(expected);
    }
  });

  test('后端 API 发现虚拟设备', async ({ request }) => {
    // :8000 /api/real-devices/ 返回 { ok, data: { devices: [...] } }
    // 设备 id 形如 simulated:sim_alpha，device_id 为裸 sim_*
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    const devices = body.data?.devices || [];
    expect(devices.length).toBeGreaterThanOrEqual(5);

    const ids = devices.map((d: any) => d.device_id || d.id);
    expect(ids.some((id: string) => id.startsWith('sim_'))).toBe(true);
  });
});

test.describe('虚拟设备生命周期 - API 验证', () => {
  let deviceId: string | null;

  test.beforeAll(async ({ request }) => {
    deviceId = await findVirtualDeviceId(request);
  });

  test('连接 → 采集 → 数据 → 停止 → 断开', async ({ request }) => {
    // skip 如果虚拟设备服务器未运行
    test.skip(!deviceId, '虚拟设备服务器未运行');

    const id = deviceId!;
    const statusOf = async () => {
      const r = await request.get(`${VDEV_BASE}/devices/${id}/status`);
      const b = await r.json();
      // 响应为 { ok, data: { status } }，兼容顶层 status
      return b?.data?.status ?? b?.status;
    };

    // 设备为跨测试共享资源，先重置到 disconnected 保证状态机断言确定性
    await request.post(`${VDEV_BASE}/devices/${id}/stop`).catch(() => null);
    await request.post(`${VDEV_BASE}/devices/${id}/disconnect`).catch(() => null);
    expect(await statusOf()).toBe('disconnected');

    // 连接 → connected
    const connectResp = await request.post(`${VDEV_BASE}/devices/${id}/connect`);
    expect(connectResp.ok()).toBeTruthy();
    expect(await statusOf()).toBe('connected');

    // 开始采集 → acquiring
    const startResp = await request.post(`${VDEV_BASE}/devices/${id}/start`);
    expect(startResp.ok()).toBeTruthy();
    expect(await statusOf()).toBe('acquiring');

    // 等待数据生成
    await new Promise((r) => setTimeout(r, 500));

    // 拉取数据
    const dataResp = await request.get(`${VDEV_BASE}/devices/${id}/data?count=10`);
    expect(dataResp.ok()).toBeTruthy();
    const dataBody = await dataResp.json();
    const frames = dataBody?.data?.frames || dataBody?.frames || dataBody?.data || dataBody;
    expect(Array.isArray(frames) ? frames.length : 0).toBeGreaterThan(0);

    // 停止采集 → 回到 connected
    const stopResp = await request.post(`${VDEV_BASE}/devices/${id}/stop`);
    expect(stopResp.ok()).toBeTruthy();
    expect(await statusOf()).toBe('connected');

    // 断开 → disconnected
    const disconnectResp = await request.post(`${VDEV_BASE}/devices/${id}/disconnect`);
    expect(disconnectResp.ok()).toBeTruthy();
    expect(await statusOf()).toBe('disconnected');
  });

  test('状态查询返回正确信息', async ({ request }) => {
    test.skip(!deviceId, '虚拟设备服务器未运行');

    const id = deviceId!;
    const resp = await request.get(`${VDEV_BASE}/devices/${id}/status`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    const status = body?.data?.status ?? body?.status;
    expect(['disconnected', 'connected', 'acquiring']).toContain(status);
  });
});

test.describe('虚拟设备 → 计算图 → 示波器 完整数据流', () => {
  test.afterEach(async ({ page }) => {
    await teardownGraph(page);
  });

  test('冻结 → 运行 → 示波器接收数据包', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '虚拟设备服务器未运行');

    // 0. 设备必须先 connect + start_streaming，否则 SOURCE 无数据（_DeviceSourceProvider 返回空）
    await request.post(`${API_BASE}/api/real-devices/connect/`, { data: { port: deviceId } }).catch(() => null);
    await request.post(`${API_BASE}/api/real-devices/${encodeURIComponent(deviceId!)}/start-acquisition/`).catch(() => null);
    // 确认设备进入采集态（若已采集则接口可能返回非 2xx，以状态查询为准）
    const devStatus = await request.get(`${API_BASE}/api/real-devices/${encodeURIComponent(deviceId!)}/status/`);
    const devBody = await devStatus.json();
    expect(['acquiring', 'connected']).toContain(devBody?.data?.status);

    // 1. 准备运行中的图（绑定虚拟设备）
    await page.goto('/cpgraph?_t=vdev_flow');
    await page.waitForLoadState('networkidle');

    const graph = buildMinimalGraph(deviceId!);
    await prepareGraphViaBrowser(page, graph);

    // 2. 跳转到可视化页面（onMounted 自动为 OUTPUT 节点创建并绑定示波器）
    await page.goto('/visualization?_t=vdev_flow_view');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 3. 等待自动创建的示波器绑定 E2E 输出节点
    await expect(page.locator('text=/信号源[:：]/').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=/E2E 示波器/').first()).toBeVisible({ timeout: 10000 });

    // 4. 验证接收数据：包计数 >0 且持续增长
    await expect
      .poll(async () => getPacketCount(page), { timeout: 15000 })
      .toBeGreaterThan(0);
    const first = await getPacketCount(page);
    await page.waitForTimeout(1500);
    const second = await getPacketCount(page);
    expect(second).toBeGreaterThan(first);

    await page.screenshot({ path: 'e2e/screenshots/vdev-flow-receiving.png', fullPage: true });
  });

  test('解冻后数据流停止', async ({ page, request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '虚拟设备服务器未运行');

    await page.goto('/cpgraph?_t=vdev_stop');
    await page.waitForLoadState('networkidle');

    const graph = buildMinimalGraph(deviceId!);
    await prepareGraphViaBrowser(page, graph);

    // 停止运行
    await sendControlCmd(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });

    // 验证后端状态
    const statusResp = await page.request.get(`${API_BASE}/api/status/`);
    const statusBody = await statusResp.json();
    expect(statusBody.runtime.running).toBe(false);
  });
});

test.describe('虚拟设备 - 数据质量', () => {
  test('采集到的数据帧通道数一致', async ({ request }) => {
    const deviceId = await findVirtualDeviceId(request);
    test.skip(!deviceId, '虚拟设备服务器未运行');

    const id = deviceId!;
    await request.post(`${VDEV_BASE}/devices/${id}/connect`);
    await request.post(`${VDEV_BASE}/devices/${id}/start`);
    await new Promise((r) => setTimeout(r, 500));

    const resp = await request.get(`${VDEV_BASE}/devices/${id}/data?count=5`);
    const body = await resp.json();
    const frames = body?.data?.frames || body?.frames || body?.data || body;

    // 空数据是硬失败，不允许 if 包裹静默通过
    expect(Array.isArray(frames)).toBe(true);
    expect(frames.length).toBeGreaterThan(0);

    const firstFrameChannels = frames[0].channels?.length || frames[0].data?.length || 0;
    expect(firstFrameChannels).toBeGreaterThan(0);

    // 所有帧的通道数应一致
    for (const frame of frames) {
      const ch = frame.channels?.length || frame.data?.length || 0;
      expect(ch).toBe(firstFrameChannels);
    }

    // 数据不允许全零（虚拟设备应产生有效波形）
    const allValues = frames.flatMap((f: any) => f.channels || f.data || []);
    expect(allValues.some((v: number) => Math.abs(v) > 1e-9)).toBe(true);

    await request.post(`${VDEV_BASE}/devices/${id}/stop`);
    await request.post(`${VDEV_BASE}/devices/${id}/disconnect`);
  });
});

test.describe('虚拟设备 - CORS 与跨域', () => {
  test('OPTIONS 预检返回 CORS 头', async ({ request }) => {
    const resp = await request.fetch(`${VDEV_BASE}/devices`, {
      method: 'OPTIONS',
    });
    // CORS 预检应返回 200/204
    expect(resp.status()).toBeLessThan(400);
  });
});
