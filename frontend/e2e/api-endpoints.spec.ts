/**
 * 后端 API 端点 E2E 测试（前后端联调）
 *
 * 系统性验证所有 HTTP API 端点的响应结构与状态码。
 * 覆盖 views.py 和 real_device_views.py 中的所有端点。
 *
 * 前提：Django 后端运行中（端口 8000）。
 */
import { test, expect } from '@playwright/test';
import { API_BASE } from './helpers';

test.describe('基础 API', () => {
  test('GET /api/health/ 返回 ok', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/health/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.status).toBe('ok');
  });

  test('GET /api/status/ 返回运行时与性能指标', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/status/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body).toHaveProperty('runtime');
    expect(body.runtime).toHaveProperty('running');
    expect(body.runtime).toHaveProperty('mode');
    expect(body.runtime).toHaveProperty('frozen');
  });

  test('GET /api/graph/ 返回图结构', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/graph/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('nodes');
    expect(body).toHaveProperty('edges');
    expect(body).toHaveProperty('frozen');
    expect(body).toHaveProperty('revision');
    expect(body).toHaveProperty('persistedRevision');
    expect(Array.isArray(body.nodes)).toBe(true);
    expect(Array.isArray(body.edges)).toBe(true);
  });

  test('POST /api/graph/ 返回 405（仅支持 GET）', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/graph/`, {
      data: { nodes: [], edges: [] },
    });
    expect(resp.status()).toBe(405);
  });

  test('GET /api/saved-files/ 返回文件列表', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/saved-files/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body).toHaveProperty('files');
  });

  test('GET /api/replayable-files/ 返回可回放文件列表', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/replayable-files/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body).toHaveProperty('files');
  });
});

test.describe('Python 节点原型 API', () => {
  test('POST /api/graph/python/prototype/ 生成原型 spec', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/graph/python/prototype/`, {
      data: {
        inputCount: 2,
        outputCount: 1,
        functionName: 'e2e_test_fn',
      },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
  });

  test('GET /api/graph/python/library/ 返回代码库', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/graph/python/library/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body).toHaveProperty('library');
  });
});

test.describe('设备管理 API', () => {
  test('GET /api/real-devices/ 返回设备列表', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
    expect(Array.isArray(body.data)).toBe(true);
  });

  test('GET /api/devices/ 兼容端点委托到 real-devices', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });

  test('GET /api/real-devices/scan-ports/ 扫描端口', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/scan-ports/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });

  test('GET /api/real-devices/status/ 设备状态', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/status/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });

  test('GET /api/real-devices/simulator/status/ 模拟器状态', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/simulator/status/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });
});

test.describe('录制 API', () => {
  test('DELETE /api/graph/record/ 停止所有录制', async ({ request }) => {
    const resp = await request.delete(`${API_BASE}/api/graph/record/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
    expect(body.recording).toBe(false);
  });
});

test.describe('错误处理', () => {
  test('GET 不存在的设备返回适当错误', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/nonexistent-device-xyz/`);
    // 应返回 404 或 ok:false
    const body = await resp.json().catch(() => ({}));
    expect(resp.status() === 404 || body.ok === false).toBeTruthy();
  });

  test('POST /api/graph/debug/ 调试端点返回 ok', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/graph/debug/`, {
      data: { test: 'e2e', timestamp: Date.now() },
    });
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
  });
});
