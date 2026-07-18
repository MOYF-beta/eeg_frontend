/**
 * 驱动故障注入 E2E 测试
 *
 * 验证前后端对驱动故障的处理与反馈：
 *   1. 后端通过 test-hook 注册/卸载 FaultyDriver
 *   2. GET /api/real-devices/ 暴露故障设备
 *   3. connect 失败返回具体 error 消息（驱动内部记录的 last_error）
 *   4. connect 失败但驱动沉默时返回兜底消息
 *   5. 抛异常的驱动不导致 500 崩溃之外的副作用（状态端点仍可用，状态=error）
 *   6. 设备状态端点暴露 last_error 字段
 *   7. 设备管理 UI 显示故障设备行 + 错误提示
 *
 * 前提：前端 dev server (5173) + Django 后端 (8000, DEBUG=True) 运行中。
 */
import { test, expect, APIRequestContext } from '@playwright/test';
import { API_BASE, teardownGraph } from './helpers';

const HOOK_URL = `${API_BASE}/api/real-devices/test-hook/faulty-driver/`;

const DEV_OK = 'flt_ok';
const DEV_CONN_ERR = 'flt_conn_err';
const DEV_THROW = 'flt_throw';
const DEV_MYSTERY = 'flt_mystery';
const DEV_FLAKY = 'flt_flaky';
const DEV_STATUS_ERR = 'flt_status_err';

async function registerFaultyDriver(request: APIRequestContext) {
  const resp = await request.post(HOOK_URL);
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body.ok).toBe(true);
  expect(body.data.registered).toBe(true);
}

async function unregisterFaultyDriver(request: APIRequestContext) {
  const resp = await request.delete(HOOK_URL);
  expect(resp.ok()).toBeTruthy();
  const body = await resp.json();
  expect(body.ok).toBe(true);
  expect(body.data.registered).toBe(false);
}

test.describe('驱动故障注入 — API 层', () => {
  test.beforeEach(async ({ request }) => {
    await registerFaultyDriver(request);
  });

  test.afterEach(async ({ request }) => {
    await unregisterFaultyDriver(request);
  });

  test('test-hook 注册后驱动列表包含 faulty', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/drivers/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    const types = body.data.drivers.map((d: any) => d.driver_type);
    expect(types).toContain('faulty');
    const faulty = body.data.drivers.find((d: any) => d.driver_type === 'faulty');
    expect(faulty.device_count).toBeGreaterThanOrEqual(6);
  });

  test('设备列表包含所有故障注入设备', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    const ids = body.data.devices.map((d: any) => d.device_id);
    for (const id of [DEV_OK, DEV_CONN_ERR, DEV_THROW, DEV_MYSTERY, DEV_FLAKY, DEV_STATUS_ERR]) {
      expect(ids).toContain(id);
    }
    // 故障设备也带 connection_status.last_error 字段
    const connErr = body.data.devices.find((d: any) => d.device_id === DEV_CONN_ERR);
    expect(connErr.connection_status).toHaveProperty('last_error');
  });

  test('connect 正常设备成功', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_OK, config: {} },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body.data.status).toBe('connected');
    expect(body.data.last_error).toBeNull();

    // 启动采集 + 读数据 + 停止 + 断开
    const startResp = await request.post(
      `${API_BASE}/api/real-devices/${DEV_OK}/start-acquisition/`,
    );
    expect(startResp.ok()).toBeTruthy();

    const statusResp = await request.get(`${API_BASE}/api/real-devices/${DEV_OK}/status/`);
    const statusBody = await statusResp.json();
    expect(statusBody.data.status).toBe('acquiring');
    expect(statusBody.data.pending_count).toBeGreaterThan(0);

    await request.post(`${API_BASE}/api/real-devices/${DEV_OK}/stop-acquisition/`);
    await request.post(`${API_BASE}/api/real-devices/${DEV_OK}/disconnect/`);
  });

  test('connect 故障设备返回 500 + 具体错误消息', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_CONN_ERR, config: {} },
    });
    expect(resp.status()).toBe(500);
    const body = await resp.json();
    expect(body.ok).toBe(false);
    // 前端能拿到具体失败原因（非笼统 "Failed to connect device"）
    expect(body.error).toContain('握手超时');
    expect(body.data.last_error).toContain('握手超时');
  });

  test('connect 沉默驱动返回兜底错误消息', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_MYSTERY, config: {} },
    });
    expect(resp.status()).toBe(500);
    const body = await resp.json();
    expect(body.ok).toBe(false);
    expect(body.error).toBe('连接失败');
  });

  test('connect 抛异常驱动被 manager 兜底，返回 500 + 异常消息', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_THROW, config: {} },
    });
    expect(resp.status()).toBe(500);
    const body = await resp.json();
    expect(body.ok).toBe(false);
    expect(body.error).toContain('connect');
  });

  test('状态自检失败设备：connect 返回 200 但 status=error + last_error', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_STATUS_ERR, config: {} },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);

    const statusResp = await request.get(`${API_BASE}/api/real-devices/${DEV_STATUS_ERR}/status/`);
    const statusBody = await statusResp.json();
    expect(statusBody.data.status).toBe('error');
    expect(statusBody.data.last_error).toContain('自检失败');

    // 启动采集失败
    const startResp = await request.post(
      `${API_BASE}/api/real-devices/${DEV_STATUS_ERR}/start-acquisition/`,
    );
    expect(startResp.status()).toBe(500);
  });

  test('间歇性设备：启动采集后缓冲帧数少于预期（丢包）', async ({ request }) => {
    await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_FLAKY, config: {} },
    });
    await request.post(`${API_BASE}/api/real-devices/${DEV_FLAKY}/start-acquisition/`);
    const resp = await request.get(`${API_BASE}/api/real-devices/${DEV_FLAKY}/status/`);
    const body = await resp.json();
    // 填充 5 帧，丢包后只剩 3 帧（验证驱动可模拟非致命数据异常）
    expect(body.data.pending_count).toBe(3);
    expect(body.data.status).toBe('acquiring');
  });

  test('抛异常驱动不破坏其他设备的状态查询', async ({ request }) => {
    // 先连接 throw 设备（会触发 manager 内部 handle_error）
    await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_THROW, config: {} },
    });
    // 设备列表仍正常返回
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    // 正常设备仍可用
    const okResp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_OK, config: {} },
    });
    expect(okResp.ok()).toBeTruthy();
    await request.post(`${API_BASE}/api/real-devices/${DEV_OK}/disconnect/`);
  });

  test('卸载 test-hook 后故障设备从列表消失', async ({ request }) => {
    await unregisterFaultyDriver(request);
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    const body = await resp.json();
    const ids = body.data.devices.map((d: any) => d.device_id);
    expect(ids).not.toContain(DEV_OK);
    expect(ids).not.toContain(DEV_CONN_ERR);
  });
});

test.describe('驱动故障注入 — 设备管理 UI', () => {
  test.beforeEach(async ({ request, page }) => {
    await registerFaultyDriver(request);
    await page.goto('/devices?_t=faulty');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1200);
  });

  test.afterEach(async ({ request, page }) => {
    await unregisterFaultyDriver(request);
    await teardownGraph(page).catch(() => null);
  });

  test('设备管理页显示故障注入驱动分组', async ({ page }) => {
    // 故障驱动应作为单独分组出现（反特例：通过驱动元信息渲染）
    await expect(page.locator('text=故障注入测试驱动')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=faulty').first()).toBeVisible();
    await page.screenshot({ path: 'e2e/screenshots/faulty-driver-group.png', fullPage: true });
  });

  test('连接故障设备后 UI 显示错误反馈', async ({ page }) => {
    // 先点击刷新加载故障设备
    await page.getByRole('button', { name: '刷新' }).first().click();
    await page.waitForTimeout(1500);

    // 找到故障设备行
    const connErrRow = page.locator('.device-row', { hasText: DEV_CONN_ERR }).first();
    await expect(connErrRow).toBeVisible({ timeout: 5000 });

    // 点击连接按钮
    const connectBtn = connErrRow.locator('button').first();
    await connectBtn.click();
    await page.waitForTimeout(1500);

    // 全局错误 alert 应出现（realDeviceApi.error 被设置）
    const errorAlert = page.locator('.v-alert[type="error"], .v-alert:has-text("握手超时")').first();
    await expect(errorAlert).toBeVisible({ timeout: 5000 });

    await page.screenshot({ path: 'e2e/screenshots/faulty-driver-connect-error.png', fullPage: true });
  });

  test('状态自检失败设备显示 error 状态 chip', async ({ page }) => {
    // 通过 API 让设备进入 ERROR 状态
    await page.request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: DEV_STATUS_ERR, config: {} },
    });

    // 刷新设备列表
    await page.getByRole('button', { name: '刷新' }).first().click();
    await page.waitForTimeout(1800);

    const errRow = page.locator('.device-row', { hasText: DEV_STATUS_ERR }).first();
    await expect(errRow).toBeVisible({ timeout: 5000 });

    // 行内应显示 last_error 文字
    await expect(errRow.locator('text=/自检失败/')).toBeVisible({ timeout: 5000 });

    await page.screenshot({ path: 'e2e/screenshots/faulty-driver-status-error.png', fullPage: true });
  });

  test('正常故障对照设备可完整连接采集', async ({ page }) => {
    await page.getByRole('button', { name: '刷新' }).first().click();
    await page.waitForTimeout(1500);

    const okRow = page.locator('.device-row', { hasText: DEV_OK }).first();
    await expect(okRow).toBeVisible({ timeout: 5000 });

    // 连接
    await okRow.locator('button').first().click();
    await page.waitForTimeout(1200);

    // 不应出现错误 alert
    const errAlert = page.locator('.v-alert:has-text("握手超时")');
    expect(await errAlert.count()).toBe(0);

    // 清理
    await page.request.post(`${API_BASE}/api/real-devices/${DEV_OK}/disconnect/`);
  });
});
