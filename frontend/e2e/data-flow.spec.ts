/**
 * 端到端数据流测试 — 从 WS 控制到 ws/eeg/ 数据推送的完整链路
 *
 * 使用合成源（SyntheticSourceProvider）和设备源（SimulatorDriver）两种方式验证。
 */
import { test, expect } from '@playwright/test';
import {
  sendControlCmd,
  sendControlCmdSafe,
  buildMinimalGraph,
} from './helpers';

const WS_CONTROL = 'ws://localhost:8000/ws/control/';
const WS_EEG = 'ws://localhost:8000/ws/eeg/';

/**
 * 在页面内监听 ws/eeg/ 数据包并返回计数
 */
async function collectEegPackets(page: any, nodeIds: string[], durationMs = 3000) {
  return await page.evaluate(
    async ({ nodeIds, durationMs, wsEegUrl }: any) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsEegUrl);
        let count = 0;
        let first: any = null;
        ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', nodeIds }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'data') {
            count++;
            if (!first) {
              first = {
                nodeId: m.nodeId,
                channels: m.channels?.length,
                sampleRate: m.sampleRate,
                hasSpectra: !!m.spectra,
                delay: m.processingDelayMs,
              };
            }
          }
        };
        setTimeout(() => { ws.close(); resolve({ count, first }); }, durationMs);
      });
    },
    { nodeIds, durationMs, wsEegUrl: WS_EEG },
  );
}

/**
 * 通过 ws/control/ 完整设置图环境：stop → unfreeze → sync → freeze → run
 */
async function fullSetup(page: any, graph: any, extraSteps?: Array<{ cmd: string; payload?: any }>) {
  await sendControlCmdSafe(page, 'stop');
  await sendControlCmdSafe(page, 'freeze', { frozen: false });

  const syncR = await sendControlCmd(page, 'sync_graph', { graph });
  expect(syncR.ok).toBe(true);

  const freezeR = await sendControlCmd(page, 'freeze', { frozen: true });
  expect(freezeR.ok).toBe(true);

  if (extraSteps) {
    for (const step of extraSteps) {
      const r = await sendControlCmd(page, step.cmd, step.payload || {});
      expect(r.ok).toBe(true);
    }
  }

  const runR = await sendControlCmd(page, 'run', { mode: 'live' });
  expect(runR.ok).toBe(true);
}

// ========================================================================== //
//  合成数据源数据流
// ========================================================================== //
test.describe('合成数据源数据流（无设备驱动）', () => {
  test('SOURCE→OUTPUT 链路产生数据包', async ({ page }) => {
    const graph = buildMinimalGraph(); // 无 deviceId，使用 SyntheticSourceProvider
    await fullSetup(page, graph);

    // 等待 engine 稳定
    await page.waitForTimeout(1000);

    const result = await collectEegPackets(page, ['e2e-output-1'], 3000);
    expect(result.count).toBeGreaterThan(0);
    expect(result.first).toBeTruthy();
    expect(result.first.nodeId).toBe('e2e-output-1');
    expect(result.first.channels).toBe(4);
    expect(result.first.sampleRate).toBe(250);
  });

  test('订阅前无数据，订阅后有数据', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    // 连接 ws/eeg/ 但不订阅
    const noSubResult = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        let count = 0;
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'data') count++;
        };
        setTimeout(() => { ws.close(); resolve(count); }, 2000);
      });
    }, WS_EEG);
    expect(noSubResult).toBe(0);

    // 现在订阅
    const result = await collectEegPackets(page, ['e2e-output-1'], 3000);
    expect(result.count).toBeGreaterThan(0);
  });

  test('数据包含频谱信息（OUTPUT 节点 FFT）', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    const result = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        let firstWithSpectra: any = null;
        ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', nodeIds: ['e2e-output-1'] }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'data' && m.spectra && !firstWithSpectra) {
            firstWithSpectra = {
              fftSize: m.fftSize,
              spectraChannels: m.spectra?.length,
              hasSpectrogram: !!m.spectrogramRow,
            };
            ws.close();
            resolve(firstWithSpectra);
          }
        };
        setTimeout(() => { ws.close(); resolve(null); }, 5000);
      });
    }, WS_EEG);

    expect(result).toBeTruthy();
    expect(result.fftSize).toBeGreaterThan(0);
    expect(result.spectraChannels).toBeGreaterThan(0);
  });

  test('停止运行后数据流停止', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    // 先确认有数据
    const before = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(before.count).toBeGreaterThan(0);

    // 停止
    await sendControlCmdSafe(page, 'stop');

    // 等 engine 清理
    await page.waitForTimeout(1000);

    const after = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(after.count).toBe(0);
  });

  test('解冻后数据流停止', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    const before = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(before.count).toBeGreaterThan(0);

    // 解冻（会先 stop）
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmd(page, 'freeze', { frozen: false });
    await page.waitForTimeout(1000);

    const after = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(after.count).toBe(0);
  });

  test('多节点订阅 — 仅 OUTPUT 类型推送数据', async ({ page }) => {
    const graph = {
      nodes: [
        { id: 'src-a', type: 'SOURCE', name: 'Source A', x: 120, y: 140, params: { channels: 2, sampleRate: 250 } },
        { id: 'out-a', type: 'OUTPUT', name: 'Output A', x: 460, y: 100, params: {} },
        { id: 'out-b', type: 'OUTPUT', name: 'Output B', x: 460, y: 300, params: {} },
      ],
      edges: [
        { id: 'e1', source: 'src-a', sourcePort: 'out', target: 'out-a', targetPort: 'in' },
        { id: 'e2', source: 'src-a', sourcePort: 'out', target: 'out-b', targetPort: 'in' },
      ],
      frozen: false,
    };
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    const result = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        const seen: string[] = [];
        ws.onopen = () => ws.send(JSON.stringify({ type: 'subscribe', nodeIds: ['out-a', 'out-b', 'src-a'] }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'data' && !seen.includes(m.nodeId)) {
            seen.push(m.nodeId);
            if (seen.length >= 2) { ws.close(); resolve(seen); }
          }
        };
        setTimeout(() => { ws.close(); resolve(seen); }, 5000);
      });
    }, WS_EEG);

    expect(result.length).toBeGreaterThanOrEqual(2);
    // SOURCE 不在订阅中推送（仅 OUTPUT）
    expect(result).not.toContain('src-a');
  });
});

// ========================================================================== //
//  虚拟设备数据流
// ========================================================================== //
test.describe('虚拟设备数据流（SimulatorDriver）', () => {
  test('设备源 SOURCE→OUTPUT 产生数据', async ({ page }) => {
    const graph = buildMinimalGraph('sim_alpha');
    await fullSetup(page, graph, [
      { cmd: 'connect_device', payload: { device_id: 'sim_alpha' } },
      { cmd: 'start_streaming', payload: { device_id: 'sim_alpha' } },
    ]);
    await page.waitForTimeout(2000);

    const result = await collectEegPackets(page, ['e2e-output-1'], 3000);
    expect(result.count).toBeGreaterThan(0);
    expect(result.first).toBeTruthy();
    expect(result.first.nodeId).toBe('e2e-output-1');
    // sim_alpha 设备实际为 8 通道（DeviceDriverManager 以驱动元数据为准）
    expect(result.first.channels).toBe(8);
  });

  test('未连接设备时 engine 回退合成源', async ({ page }) => {
    const graph = buildMinimalGraph('sim_alpha'); // 指定 deviceId 但未 connect
    await fullSetup(page, graph); // 不执行 connect_device / start_streaming
    await page.waitForTimeout(2000);

    const result = await collectEegPackets(page, ['e2e-output-1'], 3000);
    // 应该回退到合成源，仍然产生数据（方波 + 噪声）
    expect(result.count).toBeGreaterThan(0);
  });

  test('断开设备后 engine 回退合成源', async ({ page }) => {
    const graph = buildMinimalGraph('sim_alpha');
    await fullSetup(page, graph, [
      { cmd: 'connect_device', payload: { device_id: 'sim_alpha' } },
      { cmd: 'start_streaming', payload: { device_id: 'sim_alpha' } },
    ]);
    await page.waitForTimeout(2000);

    // 先确认设备源有数据
    const before = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(before.count).toBeGreaterThan(0);

    // 断开设备
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmd(page, 'disconnect_device', { device_id: 'sim_alpha' });
    await sendControlCmd(page, 'run', { mode: 'live' });
    await page.waitForTimeout(2000);

    // engine 应回退合成源
    const after = await collectEegPackets(page, ['e2e-output-1'], 2000);
    expect(after.count).toBeGreaterThan(0);
  });
});

// ========================================================================== //
//  控制通道状态同步
// ========================================================================== //
test.describe('控制通道状态同步', () => {
  test('run/stop 状态正确推送到 ws/control/ state', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    // 通过 get_state 验证
    const state = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify({ type: 'get_state' }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'state') {
            ws.close();
            resolve({
              running: m.runtime?.running,
              frozen: m.graph?.frozen,
              runtimeFrozen: m.runtime?.frozen,
            });
          }
        };
        setTimeout(() => { ws.close(); resolve(null); }, 3000);
      });
    }, WS_CONTROL);

    expect(state).toBeTruthy();
    expect(state.running).toBe(true);
    expect(state.frozen).toBe(true);
    expect(state.runtimeFrozen).toBe(true); // 修复后 runtime 也应含 frozen
  });

  test('state 推送包含 graph.frozen 且与 runtime.frozen 一致', async ({ page }) => {
    const graph = buildMinimalGraph();
    await sendControlCmdSafe(page, 'stop');
    await sendControlCmdSafe(page, 'freeze', { frozen: false });
    await sendControlCmd(page, 'sync_graph', { graph });
    await sendControlCmd(page, 'freeze', { frozen: true });
    await sendControlCmd(page, 'run', { mode: 'live' });
    await page.waitForTimeout(1000);

    const state = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify({ type: 'get_state' }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'state') {
            ws.close();
            resolve({
              graphFrozen: m.graph?.frozen,
              runtimeFrozen: m.runtime?.frozen,
              match: m.graph?.frozen === m.runtime?.frozen,
            });
          }
        };
        setTimeout(() => { ws.close(); resolve(null); }, 3000);
      });
    }, WS_CONTROL);

    expect(state).toBeTruthy();
    expect(state.graphFrozen).toBe(true);
    expect(state.runtimeFrozen).toBe(true);
    expect(state.match).toBe(true);
  });

  test('stop 后 state 中 running=false', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    await sendControlCmd(page, 'stop');
    await page.waitForTimeout(500);

    const state = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify({ type: 'get_state' }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'state') {
            ws.close();
            resolve({ running: m.runtime?.running, frozen: m.graph?.frozen });
          }
        };
        setTimeout(() => { ws.close(); resolve(null); }, 3000);
      });
    }, WS_CONTROL);

    expect(state.running).toBe(false);
    expect(state.frozen).toBe(true); // stop 不解冻
  });
});

// ========================================================================== //
//  边界情况
// ========================================================================== //
test.describe('数据流边界情况', () => {
  test('空图（无节点）冻结运行不崩溃', async ({ page }) => {
    const graph = { nodes: [], edges: [], frozen: false };
    await fullSetup(page, graph);
    await page.waitForTimeout(500);

    // 不应有任何崩溃，状态应正常
    const state = await page.evaluate(async (wsUrl: string) => {
      return new Promise((resolve) => {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => ws.send(JSON.stringify({ type: 'get_state' }));
        ws.onmessage = (ev: any) => {
          const m = JSON.parse(ev.data);
          if (m.type === 'state') {
            ws.close();
            resolve(m.runtime?.running);
          }
        };
        setTimeout(() => { ws.close(); resolve(null); }, 3000);
      });
    }, WS_CONTROL);
    expect(state).toBe(true);
  });

  test('仅 SOURCE 无 OUTPUT 的图不崩溃', async ({ page }) => {
    const graph = {
      nodes: [{ id: 'src1', type: 'SOURCE', name: 'OnlySrc', x: 120, y: 140, params: { channels: 2, sampleRate: 100 } }],
      edges: [],
      frozen: false,
    };
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    const result = await collectEegPackets(page, ['src1'], 2000);
    // SOURCE 不会被推送（只有 OUTPUT 类型）
    expect(result.count).toBe(0);
  });

  test('多次 run/stop 循环不泄漏', async ({ page }) => {
    const graph = buildMinimalGraph();
    await fullSetup(page, graph);
    await page.waitForTimeout(500);

    for (let i = 0; i < 3; i++) {
      const result = await collectEegPackets(page, ['e2e-output-1'], 1000);
      expect(result.count).toBeGreaterThan(0);

      await sendControlCmd(page, 'stop');
      await page.waitForTimeout(500);

      const afterStop = await collectEegPackets(page, ['e2e-output-1'], 500);
      expect(afterStop.count).toBe(0);

      const runR = await sendControlCmd(page, 'run', { mode: 'live' });
      expect(runR.ok).toBe(true);
      await page.waitForTimeout(500);
    }
  });

  test('采样率配置生效', async ({ page }) => {
    const graph = {
      nodes: [
        { id: 'src1', type: 'SOURCE', name: 'Fast', x: 120, y: 140, params: { channels: 1, sampleRate: 1000 } },
        { id: 'out1', type: 'OUTPUT', name: 'FastOut', x: 460, y: 140, params: {} },
      ],
      edges: [{ id: 'e1', source: 'src1', sourcePort: 'out', target: 'out1', targetPort: 'in' }],
      frozen: false,
    };
    await fullSetup(page, graph);
    await page.waitForTimeout(2000);

    const result = await collectEegPackets(page, ['out1'], 2000);
    expect(result.count).toBeGreaterThan(0);
    expect(result.first.sampleRate).toBe(1000);
  });

  test('多通道配置生效', async ({ page }) => {
    const graph = {
      nodes: [
        { id: 'src1', type: 'SOURCE', name: 'Multi', x: 120, y: 140, params: { channels: 8, sampleRate: 250 } },
        { id: 'out1', type: 'OUTPUT', name: 'MultiOut', x: 460, y: 140, params: {} },
      ],
      edges: [{ id: 'e1', source: 'src1', sourcePort: 'out', target: 'out1', targetPort: 'in' }],
      frozen: false,
    };
    await fullSetup(page, graph);
    await page.waitForTimeout(1000);

    const result = await collectEegPackets(page, ['out1'], 3000);
    expect(result.count).toBeGreaterThan(0);
    expect(result.first.channels).toBe(8);
  });
});
