/**
 * Playwright E2E 测试通用辅助函数
 *
 * 汇集跨 spec 复用的工具：API 调用、图准备、页面导航、数据包计数。
 *
 * 重要：图的修改/冻结/运行统一通过 WebSocket ws/control/ 进行，
 * HTTP /api/graph/ 仅支持 GET。本模块封装 WS 交互（在浏览器页面内执行）。
 */
import type { Page, APIRequestContext } from '@playwright/test';
import { expect } from '@playwright/test';

export const API_BASE = 'http://localhost:8000';
export const WS_BASE = 'ws://localhost:8000';

/** 最小调试图：SOURCE -> OUTPUT，便于联调测试使用 */
export function buildMinimalGraph(deviceId?: string) {
  const sourceId = 'e2e-source-1';
  const outputId = 'e2e-output-1';
  return {
    nodes: [
      {
        id: sourceId,
        type: 'SOURCE',
        name: 'E2E 数据源',
        x: 120,
        y: 140,
        deviceId: deviceId || null,
        params: {
          sourceMode: 'live',
          sampleRate: 250,
          channels: 4,
          deviceId: deviceId || null,
        },
      },
      {
        id: outputId,
        type: 'OUTPUT',
        name: 'E2E 示波器',
        x: 460,
        y: 140,
        params: { timeWindow: 5, mode: 'scroll', saveEnabled: false },
      },
    ],
    edges: [
      {
        id: 'e2e-edge-1',
        source: sourceId,
        sourcePort: 'out',
        target: outputId,
        targetPort: 'in',
      },
    ],
    frozen: false,
  };
}

/**
 * 在浏览器页面内通过 ws/control/ 发送命令并等待 cmd_result。
 */
export async function sendControlCmd(
  page: Page,
  command: string,
  payload: Record<string, unknown> = {},
  timeoutMs = 5000,
): Promise<Record<string, any>> {
  return await page.evaluate(
    async ({ command, payload, wsUrl, timeoutMs }) => {
      return await new Promise<Record<string, any>>((resolve, reject) => {
        const timer = setTimeout(() => {
          try { ws.close(); } catch { /* noop */ }
          reject(new Error(`WS command '${command}' timed out after ${timeoutMs}ms`));
        }, timeoutMs);

        const ws = new WebSocket(wsUrl);
        ws.onopen = () => {
          ws.send(JSON.stringify({ type: command, ...payload }));
        };
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'cmd_result' && msg.command === command) {
              clearTimeout(timer);
              ws.close();
              resolve(msg);
            }
            // 其他消息（state / 心跳）忽略
          } catch { /* ignore */ }
        };
        ws.onerror = () => {
          clearTimeout(timer);
          reject(new Error(`WS error for '${command}'`));
        };
      });
    },
    { command, payload, wsUrl: `${WS_BASE}/ws/control/`, timeoutMs },
  );
}

/** 发送命令但不抛错（用于清理 / 幂等操作） */
export async function sendControlCmdSafe(
  page: Page,
  command: string,
  payload: Record<string, unknown> = {},
) {
  try {
    return await sendControlCmd(page, command, payload, 3000);
  } catch {
    return null;
  }
}

/**
 * 通过浏览器页面 WS 准备一张图：sync_graph → freeze → run。
 */
export async function prepareGraphViaBrowser(
  page: Page,
  graph: Record<string, unknown>,
) {
  await sendControlCmdSafe(page, 'stop');
  await sendControlCmdSafe(page, 'freeze', { frozen: false });

  const syncResult = await sendControlCmd(page, 'sync_graph', { graph });
  if (!syncResult.ok) {
    throw new Error(`sync_graph 失败: ${JSON.stringify(syncResult)}`);
  }

  const freezeResult = await sendControlCmd(page, 'freeze', { frozen: true });
  if (!freezeResult.ok) {
    throw new Error(`freeze 失败: ${JSON.stringify(freezeResult)}`);
  }

  const runResult = await sendControlCmd(page, 'run', { mode: 'live' });
  if (!runResult.ok) {
    throw new Error(`run 失败: ${JSON.stringify(runResult)}`);
  }
}

/** 停止运行并解冻，清理后端状态 */
export async function teardownGraph(page: Page) {
  await sendControlCmdSafe(page, 'stop');
  await sendControlCmdSafe(page, 'freeze', { frozen: false });
}

/** 等待数据包计数（正则匹配 `接收: N 包` / `接收 N 包` 等） */
export async function getPacketCount(page: Page): Promise<number> {
  try {
    const text = await page
      .locator('text=/接收[^]*\\d+[^]*包/')
      .first()
      .textContent({ timeout: 5000 });
    if (!text) return 0;
    const match = text.match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  } catch {
    return 0;
  }
}

/** 通过 API 获取虚拟设备 deviceId（sim_*），设备需已运行 */
export async function findVirtualDeviceId(api: APIRequestContext): Promise<string | null> {
  const resp = await api.get(`${API_BASE}/api/real-devices/`);
  if (!resp.ok()) return null;
  const body = await resp.json();
  // 响应结构：{data: {devices: [...], count: N}} 或 {data: [...]}
  let devices: any[] = [];
  const data = body?.data;
  if (Array.isArray(data)) {
    devices = data;
  } else if (data && Array.isArray(data.devices)) {
    devices = data.devices;
  }
  const sim = devices.find((d: any) =>
    String(d?.id || d?.device_id || '').includes('sim_'),
  );
  if (sim) {
    // 设备 id 格式为 "simulated:sim_alpha"，提取原始 device_id
    const rawId = String(sim.id || sim.device_id || '');
    // 如果是 "simulated:sim_alpha" 格式，取冒号后的部分
    const colonIdx = rawId.indexOf(':');
    return colonIdx >= 0 ? rawId.substring(colonIdx + 1) : rawId;
  }
  return null;
}

/** 点击侧边栏导航（rail 折叠态，只能点击图标 v-list-item） */
export async function clickSidebarNav(page: Page, title: string) {
  const item = page.locator(`.v-list-item[title="${title}"], a[title="${title}"]`).first();
  if (await item.count()) {
    await item.click();
    await page.waitForLoadState('networkidle');
    return;
  }
  const routeMap: Record<string, string> = {
    计算图工作台: '/cpgraph',
    可视化: '/visualization',
    开发目录: '/dev',
  };
  const route = routeMap[title];
  if (route) {
    await page.goto(route);
    await page.waitForLoadState('networkidle');
  }
}

/** 等待计算图页面就绪 */
export async function waitForGraphEditor(page: Page) {
  await page.waitForLoadState('networkidle');
  await expect
    .poll(async () => page.locator('text=计算图编辑器').count())
    .toBeGreaterThan(0);
}

/** 获取后端运行时状态（通过 /api/status/） */
export async function getBackendStatus(
  api: APIRequestContext,
): Promise<{ running: boolean; frozen: boolean; mode: string }> {
  const resp = await api.get(`${API_BASE}/api/status/`);
  if (!resp.ok()) return { running: false, frozen: false, mode: 'live' };
  const body = await resp.json();
  const runtime = body?.runtime || {};
  return {
    running: !!runtime.running,
    frozen: !!runtime.frozen,
    mode: String(runtime.mode || 'live'),
  };
}

/** 通过后端串口模拟器启动并返回 port + deviceId */
export async function startSimulatorAndConnect(
  api: APIRequestContext,
  sampleRate = 1000,
  channels = 8,
): Promise<{ port: string; deviceId: string }> {
  const simResp = await api.post(`${API_BASE}/api/real-devices/simulator/start/`, {
    data: { sample_rate: sampleRate, channels },
  });
  expect(simResp.ok()).toBeTruthy();
  const simJson = await simResp.json();
  const port = String(simJson?.data?.port || '');
  expect(port.length).toBeGreaterThan(0);

  await api.post(`${API_BASE}/api/real-devices/connect/`, {
    data: { port, baudrate: 460800 },
  });

  const devicesResp = await api.get(`${API_BASE}/api/devices/`);
  const devicesJson = await devicesResp.json();
  const devices = Array.isArray(devicesJson?.data) ? devicesJson.data : [];
  const realDevice = devices.find((d: any) => String(d?.config?.port || '') === port);
  expect(realDevice).toBeTruthy();
  return { port, deviceId: String(realDevice.id) };
}

/** 清理模拟器与设备连接 */
export async function cleanupSimulator(api: APIRequestContext, port: string) {
  await api
    .post(`${API_BASE}/api/real-devices/${encodeURIComponent(port)}/disconnect/`)
    .catch(() => null);
  await api
    .post(`${API_BASE}/api/real-devices/simulator/stop/`, { data: { port } })
    .catch(() => null);
}
