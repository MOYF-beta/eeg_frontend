/**
 * 长时间反复启停会话 E2E 测试
 *
 * 模拟用户反复「修改计算图 → 运行 → 观察 → 停止 → 再修改」的真实调试工作流，
 * 持续多轮，重点暴露：
 *   - 反复启停导致的状态泄漏（后端 running 标志、图引擎 worker 线程残留）
 *   - 订阅残留 / WebSocket 重连风暴
 *   - stop 后画布未恢复可编辑、或残留的「冻结」态导致后续 run 被锁
 *   - 反复 sync_graph 的 revision 冲突累积
 *
 * 前提：Django 后端（8000）+ 前端 dev server（5173）运行中。
 *
 * 说明：这是重度测试（默认 15 轮，每轮含 ~8s 运行观察），总时长数分钟。
 * 可通过环境变量 LONG_SESSION_ROUNDS 调整轮数。
 */
import { test, expect } from '@playwright/test';
import {
  sendControlCmd,
  sendControlCmdSafe,
  teardownGraph,
  API_BASE,
  WS_BASE,
} from './helpers';

// 轮数（默认 15，可用环境变量覆盖以便本地快速验证）
const ROUNDS = Number(process.env.LONG_SESSION_ROUNDS || 15);
// 每轮运行观察时长（ms）
const RUN_OBSERVE_MS = Number(process.env.LONG_SESSION_RUN_MS || 8000);

/** 构造第 round 轮的图：SOURCE -> OUTPUT，sampleRate 随轮次变化模拟用户修改参数 */
function buildRoundGraph(round: number) {
  const sourceId = 'ls-source-1';
  const outputId = 'ls-output-1';
  return {
    nodes: [
      {
        id: sourceId,
        type: 'SOURCE',
        name: `长会话源 r${round}`,
        x: 120,
        y: 140,
        deviceId: null,
        params: {
          // 每轮微调采样率/通道，模拟用户反复调参
          sampleRate: 200 + (round % 5) * 50,
          channels: 2 + (round % 3),
        },
      },
      {
        id: outputId,
        type: 'OUTPUT',
        name: '长会话示波器',
        x: 460,
        y: 140,
        params: { timeWindow: 5, mode: 'scroll', saveEnabled: false },
      },
    ],
    edges: [
      {
        id: 'ls-edge-1',
        source: sourceId,
        sourcePort: 'out',
        target: outputId,
        targetPort: 'in',
      },
    ],
    frozen: false,
  };
}

/** 在页面内订阅 ws/eeg/ 并在 timeoutMs 内统计收到的 data 包数量，结束时主动退订释放连接 */
async function countDataPackets(page: any, nodeId: string, timeoutMs: number): Promise<number> {
  return await page.evaluate(
    async ({ nodeId, timeoutMs, wsUrl }) => {
      return await new Promise<number>((resolve) => {
        let count = 0;
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', nodeIds: [nodeId] }));
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'data' && msg.nodeId === nodeId) count++;
          } catch { /* ignore */ }
        };
        setTimeout(() => {
          try { ws.send(JSON.stringify({ type: 'unsubscribe', nodeIds: [nodeId] })); } catch { /* noop */ }
          setTimeout(() => {
            try { ws.close(); } catch { /* noop */ }
            resolve(count);
          }, 150);
        }, timeoutMs);
      });
    },
    { nodeId, timeoutMs, wsUrl: `${WS_BASE}/ws/eeg/` },
  );
}

/** 读取后端 /api/status/ 的运行态 */
async function getBackendRunning(page: any): Promise<boolean> {
  const resp = await page.request.get(`${API_BASE}/api/status/`);
  const body = await resp.json();
  return Boolean(body?.runtime?.running);
}

test.describe('长时间反复启停会话', () => {
  // 重度测试：提高超时到 30 分钟以容纳 15 轮 × ~10s
  test.setTimeout(30 * 60 * 1000);

  test.afterEach(async ({ page }) => {
    await teardownGraph(page).catch(() => null);
  });

  test(`反复 修改→运行→停止 ${ROUNDS} 轮不出现状态泄漏`, async ({ page }) => {
    await page.goto('/cpgraph?_t=long_session');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    const stats = {
      rounds: 0,
      runOk: 0,
      stopOk: 0,
      dataRounds: 0,
      stuckRunning: 0, // stop 后后端仍 running 的次数（状态泄漏信号）
    };

    for (let round = 1; round <= ROUNDS; round++) {
      // ---- 修改图（模拟用户调参） ----
      const graph = buildRoundGraph(round);
      const sync = await sendControlCmd(page, 'sync_graph', { graph });
      expect(sync.ok).toBe(true);

      // ---- 运行 ----
      const run = await sendControlCmd(page, 'run', { mode: 'live' });
      expect(run.ok).toBe(true);
      if (run.ok) stats.runOk++;

      // ---- 运行观察：订阅 OUTPUT，确认有实时数据流出 ----
      const packets = await countDataPackets(page, 'ls-output-1', RUN_OBSERVE_MS);
      if (packets > 0) stats.dataRounds++;

      // ---- 停止 ----
      const stop = await sendControlCmd(page, 'stop');
      if (stop?.ok) stats.stopOk++;

      // ---- 校验停止生效（后端 running 应为 false，无卡死残留） ----
      // 给后端短暂收敛时间
      await page.waitForTimeout(300);
      const stillRunning = await getBackendRunning(page);
      if (stillRunning) stats.stuckRunning++;

      stats.rounds = round;
    }

    // 汇总断言
    expect(stats.rounds).toBe(ROUNDS);
    expect(stats.runOk).toBe(ROUNDS);
    expect(stats.stopOk).toBe(ROUNDS);
    // 绝大多数轮次应有数据（允许个别轮因时序丢帧，但 >= 80%）
    expect(stats.dataRounds).toBeGreaterThanOrEqual(Math.ceil(ROUNDS * 0.8));
    // 关键：stop 后后端绝不应卡在 running（这是反复启停最常见的状态泄漏）
    expect(stats.stuckRunning).toBe(0);

    console.log('[long-session] stats =', JSON.stringify(stats));
  });

  test('快速连续 run/stop 不崩溃且最终停在可编辑态', async ({ page }) => {
    test.setTimeout(5 * 60 * 1000);
    await page.goto('/cpgraph?_t=rapid_toggle');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);

    await sendControlCmd(page, 'sync_graph', { graph: buildRoundGraph(1) });

    // 快速连续切换（模拟用户快速点击运行/停止）
    for (let i = 0; i < 10; i++) {
      await sendControlCmdSafe(page, 'run', { mode: 'live' });
      await page.waitForTimeout(150);
      await sendControlCmdSafe(page, 'stop');
      await page.waitForTimeout(150);
    }

    // 最终应收敛到非运行态（可编辑）
    await page.waitForTimeout(1000);
    const running = await getBackendRunning(page);
    expect(running).toBe(false);

    // 快速启停后仍能正常 sync（图未被锁死）
    const sync = await sendControlCmd(page, 'sync_graph', { graph: buildRoundGraph(2) });
    expect(sync.ok).toBe(true);
  });
});
