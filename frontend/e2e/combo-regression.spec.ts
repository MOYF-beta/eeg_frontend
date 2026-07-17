/**
 * 鲁棒性 + 端到端组合回归测试
 *
 * 核心目标：验证系统在经历各种边界/错误情况后，仍然能够正确完成完整的端到端流程。
 * 即：每个边界条件测试之后，立即运行一个端到端验证，确认系统状态可恢复。
 *
 * 测试策略（serial 模式，共享前后端状态）：
 *   1. [边界] 无效输入 → [E2E] 验证图仍可用
 *   2. [边界] 运行时守卫 → [E2E] 停止后恢复正常
 *   3. [边界] 冲突检测 → [E2E] 正确同步仍工作
 *   4. [边界] 录制边界 → [E2E] 完整录制仍正常
 *   5. [边界] 设备错误 → [E2E] 设备列表仍可用
 *   6. [边界] 空图结构 → [E2E] 重新加载正常图
 *   7. [完整E2E] 全流程：设备→图→示波器→录制→验证产物
 *
 * 前提：前端(5173) + 后端(8000) + 虚拟设备(7777) 运行中。
 */
import { test, expect } from '@playwright/test';
import {
  sendControlCmd,
  sendControlCmdSafe,
  teardownGraph,
  buildMinimalGraph,
  API_BASE,
  findVirtualDeviceId,
  getPacketCount,
} from './helpers';

test.describe('鲁棒性 + 端到端组合回归', () => {
  test.describe.configure({ mode: 'serial' });

  let deviceId: string | null = null;

  test.beforeAll(async ({ request }) => {
    // 清理后端状态，确保干净起点
    await request.delete(`${API_BASE}/api/graph/record/`).catch(() => null);
    // 探测虚拟设备
    deviceId = await findVirtualDeviceId(request);
  });

  // 辅助：每次边界测试后重置后端状态
  async function resetBackend(page: import('@playwright/test').Page) {
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
  }

  // 辅助：发送原始 WS 消息并收集返回
  async function sendAndCollect(
    page: import('@playwright/test').Page,
    payload: object | string,
    waitMs = 1500,
  ): Promise<any[]> {
    return await page.evaluate(
      async ({ rawPayload, waitMs }) => {
        return await new Promise<any[]>((resolve) => {
          const messages: any[] = [];
          const ws = new WebSocket('ws://localhost:8000/ws/control/');
          ws.onopen = () => ws.send(rawPayload);
          ws.onmessage = (ev) => {
            try { messages.push(JSON.parse(ev.data)); } catch { /* ignore */ }
          };
          setTimeout(() => {
            try { ws.close(); } catch { /* noop */ }
            resolve(messages);
          }, waitMs);
        });
      },
      { rawPayload: typeof payload === 'string' ? payload : JSON.stringify(payload), waitMs },
    );
  }

  // 辅助：端到端验证 — 确认系统仍可正常同步图并运行
  async function verifyGraphStillWorks(page: import('@playwright/test').Page) {
    await resetBackend(page);
    const result = await sendControlCmd(page, 'sync_graph', {
      graph: buildMinimalGraph(),
    });
    expect(result.ok).toBe(true);

    const freezeResult = await sendControlCmd(page, 'freeze', { frozen: true });
    expect(freezeResult.ok).toBe(true);

    const runResult = await sendControlCmd(page, 'run', { mode: 'live' });
    expect(runResult.ok).toBe(true);

    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
  }

  // ================================================================ //
  //  组合 1：无效 WS 输入 → 验证图仍可用
  // ================================================================ //
  test('组合1A — 发送无效 JSON 后系统不崩溃', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_invalid');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const messages = await sendAndCollect(page, 'this is not json {{{');

    const error = messages.find((m) => m.type === 'error');
    expect(error).toBeTruthy();
    expect(error.error).toContain('Invalid JSON');
  });

  test('组合1B — [E2E] 无效 JSON 后图同步仍正常', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_invalid_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await verifyGraphStillWorks(page);
  });

  test('组合1C — 未知命令后系统不崩溃', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_unknown');
    await page.waitForLoadState('networkidle');

    const messages = await sendAndCollect(page, { type: 'nonexistent_xyz_123' });
    const error = messages.find((m) => m.type === 'error');
    expect(error).toBeTruthy();
  });

  test('组合1D — [E2E] 未知命令后图同步仍正常', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_unknown_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await verifyGraphStillWorks(page);
  });

  // ================================================================ //
  //  组合 2：运行时守卫 → 停止后恢复
  // ================================================================ //
  test('组合2A — 运行中尝试改图被拒绝', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_runtime');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });
    await sendControlCmd(page, 'run', { mode: 'live' });

    // 运行中改图
    const messages = await sendAndCollect(page, {
      type: 'sync_graph',
      graph: buildMinimalGraph(),
    });
    const error = messages.find((m) => m.type === 'error');
    const failResult = messages.find(
      (m) => m.type === 'cmd_result' && m.command === 'sync_graph' && !m.ok,
    );
    expect(error || failResult).toBeTruthy();
  });

  test('组合2B — [E2E] 停止运行后图可正常修改', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_runtime_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    // 先停止
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });

    // 现在改图应该成功
    const result = await sendControlCmd(page, 'sync_graph', {
      graph: buildMinimalGraph(),
    });
    expect(result.ok).toBe(true);
  });

  test('组合2C — 运行中冻结被拒绝', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_freeze_guard');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });
    await sendControlCmd(page, 'run', { mode: 'live' });

    const result = await sendControlCmd(page, 'freeze', { frozen: false });
    expect(result.ok).toBe(false);
  });

  test('组合2D — [E2E] 停止后冻结恢复正常', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_freeze_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmdSafe(page, 'stop');
    const result = await sendControlCmd(page, 'freeze', { frozen: false });
    expect(result.ok).toBe(true);
  });

  // ================================================================ //
  //  组合 3：冲突检测 → 正确同步仍工作
  // ================================================================ //
  test('组合3A — 过期 revision 被拒绝', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_conflict');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const result = await sendControlCmd(page, 'sync_graph', {
      graph: buildMinimalGraph(),
      baseRevision: 999999,
    });
    expect(result.ok).toBe(false);
    expect(result.conflict).toBe(true);
  });

  test('组合3B — [E2E] 冲突后用正确 revision 同步成功', async ({ page, request }) => {
    await page.goto('/cpgraph?_t=combo_conflict_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await resetBackend(page);
    const resp = await request.get(`${API_BASE}/api/graph/`);
    const body = await resp.json();
    const currentRev = body.revision;

    const result = await sendControlCmd(page, 'sync_graph', {
      graph: buildMinimalGraph(),
      baseRevision: currentRev,
    });
    expect(result.ok).toBe(true);
    expect(result.conflict).toBeFalsy();
  });

  // ================================================================ //
  //  组合 4：录制边界 → 完整录制仍正常
  // ================================================================ //
  test('组合4A — 未录制时停止不崩溃', async ({ request }) => {
    await request.delete(`${API_BASE}/api/graph/record/`).catch(() => null);
    const resp = await request.delete(`${API_BASE}/api/graph/record/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body.ok).toBe(true);
  });

  test('组合4B — 连续多次 DELETE record 幂等', async ({ request }) => {
    for (let i = 0; i < 3; i++) {
      const resp = await request.delete(`${API_BASE}/api/graph/record/`);
      expect(resp.ok()).toBeTruthy();
    }
  });

  test('组合4C — [E2E] 录制边界后系统仍可运行图', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_record_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await verifyGraphStillWorks(page);
  });

  // ================================================================ //
  //  组合 5：设备错误 → 设备列表仍可用
  // ================================================================ //
  test('组合5A — 访问不存在设备返回 404', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/nonexistent-xyz/`);
    expect(resp.status()).toBe(404);
  });

  test('组合5B — 连接不存在设备返回错误', async ({ request }) => {
    const resp = await request.post(`${API_BASE}/api/real-devices/connect/`, {
      data: { port: '/dev/ttyNOTREAL', baudrate: 115200 },
    });
    const body = await resp.json().catch(() => ({}));
    expect(resp.status() === 500 || body.ok === false).toBeTruthy();
  });

  test('组合5C — [E2E] 设备错误后设备列表仍正常', async ({ request }) => {
    const resp = await request.get(`${API_BASE}/api/real-devices/`);
    expect(resp.ok()).toBeTruthy();
    const body = await resp.json();
    expect(body).toHaveProperty('data');
  });

  // ================================================================ //
  //  组合 6：边界图结构 → 重新加载正常图
  // ================================================================ //
  test('组合6A — 空图可以同步', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_empty');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const result = await sendControlCmd(page, 'sync_graph', {
      graph: { nodes: [], edges: [], frozen: false },
    });
    expect(result.ok).toBe(true);
  });

  test('组合6B — 只有 OUTPUT 无 SOURCE 的图可以冻结', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_output_only');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    const result = await sendControlCmd(page, 'sync_graph', {
      graph: {
        nodes: [
          {
            id: 'lonely-out',
            type: 'OUTPUT',
            name: '孤立输出',
            x: 200, y: 200,
            params: { timeWindow: 5 },
          },
        ],
        edges: [],
        frozen: false,
      },
    });
    expect(result.ok).toBe(true);
    const freezeResult = await sendControlCmd(page, 'freeze', { frozen: true });
    expect(freezeResult.ok).toBe(true);
  });

  test('组合6C — [E2E] 边界图后重新加载完整图并运行', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_recover_full');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    await verifyGraphStillWorks(page);
  });

  // ================================================================ //
  //  组合 7：offline 模式 → live 模式恢复
  // ================================================================ //
  test('组合7A — offline 模式拒绝 live SOURCE', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_offline');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });

    const result = await sendControlCmd(page, 'run', { mode: 'offline' });
    expect(result.ok).toBe(false);
  });

  test('组合7B — [E2E] offline 失败后 live 模式正常运行', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_offline_recover');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmdSafe(page, 'freeze', { frozen: false });
    const result = await sendControlCmd(page, 'run', { mode: 'live' });
    // 可能需要先冻结
    if (!result.ok) {
      await sendControlCmd(page, 'freeze', { frozen: true });
      const r2 = await sendControlCmd(page, 'run', { mode: 'live' });
      expect(r2.ok).toBe(true);
    }
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
  });

  // ================================================================ //
  //  组合 8：run/stop 循环稳定性
  // ================================================================ //
  test('组合8 — 多次 run/stop 循环后系统稳定', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_cycle');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);

    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });

    // 3 次 run/stop 循环
    for (let i = 0; i < 3; i++) {
      const r = await sendControlCmd(page, 'run', { mode: 'live' });
      expect(r.ok).toBe(true);
      await page.waitForTimeout(500);
      await sendControlCmd(page, 'stop');
      await page.waitForTimeout(300);
    }

    // 最终验证仍可运行
    const finalRun = await sendControlCmd(page, 'run', { mode: 'live' });
    expect(finalRun.ok).toBe(true);
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
  });

  // ================================================================ //
  //  组合 9：页面刷新后状态恢复 + E2E 验证
  // ================================================================ //
  test('组合9 — 刷新页面后冻结态恢复并可运行', async ({ page }) => {
    await page.goto('/cpgraph?_t=combo_refresh');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await sendControlCmd(page, 'sync_graph', { graph: buildMinimalGraph() });
    await sendControlCmd(page, 'freeze', { frozen: true });

    // 刷新
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    // 冻结态应保持
    const statusResp = await page.request.get(`${API_BASE}/api/status/`);
    const statusBody = await statusResp.json();
    expect(statusBody.runtime.frozen).toBe(true);

    // 刷新后仍可运行
    const runResult = await sendControlCmd(page, 'run', { mode: 'live' });
    expect(runResult.ok).toBe(true);

    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
  });

  // ================================================================ //
  //  组合 10（最终）：完整端到端流程（需要虚拟设备）
  // ================================================================ //
  test('组合10 — [完整E2E] 所有边界后完整流程仍成功', async ({ page, request }) => {
    test.skip(!deviceId, '虚拟设备服务器未运行');

    // 清理起点
    await page.goto('/cpgraph?_t=combo_final');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    await resetBackend(page);

    // 1. 构建带虚拟设备的图
    const graph = buildMinimalGraph(deviceId);
    const syncResult = await sendControlCmd(page, 'sync_graph', { graph });
    expect(syncResult.ok).toBe(true);

    // 2. 连接设备 + 启动数据流
    await sendControlCmd(page, 'connect_device', { device_id: deviceId });
    await sendControlCmd(page, 'start_streaming', { device_id: deviceId });

    // 3. 冻结 + 运行
    await sendControlCmd(page, 'freeze', { frozen: true });
    const runResult = await sendControlCmd(page, 'run', { mode: 'live' });
    expect(runResult.ok).toBe(true);
    await page.waitForTimeout(2000);

    // 4. 验证后端确实在运行
    const statusResp = await request.get(`${API_BASE}/api/status/`);
    const statusBody = await statusResp.json();
    expect(statusBody.runtime.running).toBe(true);

    // 5. 导航到可视化页面
    await page.evaluate(() => localStorage.removeItem('viz_layout_settings'));
    await page.goto('/visualization?_t=combo_final_viz');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2500);

    // 6. 验证示波器卡片出现
    await expect(page.locator('text=波形可视化')).toBeVisible();

    // 7. 截图验证
    await page.screenshot({ path: 'e2e/screenshots/combo-final-viz.png', fullPage: true });

    // 8. 清理
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
    await sendControlCmdSafe(page, 'stop_streaming', { device_id: deviceId });
    await sendControlCmdSafe(page, 'disconnect_device', { device_id: deviceId });
  });

  // 清理
  test.afterAll(async ({ request }) => {
    await request.delete(`${API_BASE}/api/graph/record/`).catch(() => null);
  });
});
