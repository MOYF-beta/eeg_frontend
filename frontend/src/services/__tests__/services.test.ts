// SessionStore 纯函数单元测试（标准 vitest）
// 覆盖：设备/示波器管理、节点映射绑定、validateFreeze 冻结校验。
// 不触碰需要后端的 WebSocket / Runtime（属集成范畴，由 e2e 覆盖）。
import { describe, it, expect, beforeEach } from 'vitest';
import { sessionStore, type Device, type Oscilloscope } from '../sessionStore';
import type { GraphNode } from '../graph';

function makeDevice(id: string, overrides: Partial<Device> = {}): Device {
  return {
    id,
    name: `设备-${id}`,
    status: 'online',
    samplingRate: 250,
    channelCount: 4,
    type: 'simulated',
    config: {},
    ...overrides,
  };
}

function makeOsc(id: string, overrides: Partial<Oscilloscope> = {}): Oscilloscope {
  return { id, name: `示波器-${id}`, isActive: true, timeWindow: 5, yScale: 1, ...overrides };
}

beforeEach(() => {
  sessionStorage.clear();
  sessionStore.clear();
});

describe('sessionStore 设备管理', () => {
  it('setDevices / getDevices / getDeviceById', () => {
    sessionStore.setDevices([makeDevice('dev1'), makeDevice('dev2', { status: 'offline' })]);
    expect(sessionStore.getDevices()).toHaveLength(2);
    expect(sessionStore.getDeviceById('dev1')?.name).toBe('设备-dev1');
    expect(sessionStore.getDeviceById('dev2')?.status).toBe('offline');
    expect(sessionStore.getDeviceById('nonexistent')).toBeUndefined();
  });

  it('updateDeviceStatus 更新指定设备状态', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    sessionStore.updateDeviceStatus('dev1', 'offline');
    expect(sessionStore.getDeviceById('dev1')?.status).toBe('offline');
  });
});

describe('sessionStore 示波器管理', () => {
  it('setOscilloscopes / getOscilloscopes', () => {
    sessionStore.setOscilloscopes([makeOsc('osc1'), makeOsc('osc2', { isActive: false })]);
    expect(sessionStore.getOscilloscopes()).toHaveLength(2);
    expect(sessionStore.getOscilloscopeById('osc2')?.isActive).toBe(false);
  });
});

describe('sessionStore 节点映射绑定', () => {
  it('bindInputNode 成功绑定已存在设备', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    expect(sessionStore.bindInputNode('node1', 'dev1')).toBe(true);
    expect(sessionStore.getInputNodeDevice('node1')?.id).toBe('dev1');
  });

  it('bindInputNode 拒绝绑定不存在设备', () => {
    expect(sessionStore.bindInputNode('node1', 'ghost')).toBe(false);
    expect(sessionStore.getInputNodeDevice('node1')).toBeUndefined();
  });

  it('bindOutputNode 成功并回填 targetNodeId', () => {
    sessionStore.setOscilloscopes([makeOsc('osc1')]);
    expect(sessionStore.bindOutputNode('node2', 'osc1')).toBe(true);
    expect(sessionStore.getOutputNodeOscilloscope('node2')?.id).toBe('osc1');
    expect(sessionStore.getOscilloscopeById('osc1')?.targetNodeId).toBe('node2');
  });

  it('unbindInputNode / unbindOutputNode 解除映射', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    sessionStore.setOscilloscopes([makeOsc('osc1')]);
    sessionStore.bindInputNode('node1', 'dev1');
    sessionStore.bindOutputNode('node2', 'osc1');

    sessionStore.unbindInputNode('node1');
    expect(sessionStore.getInputNodeDevice('node1')).toBeUndefined();

    sessionStore.unbindOutputNode('node2');
    expect(sessionStore.getOutputNodeOscilloscope('node2')).toBeUndefined();
    // 解绑输出应清除示波器上的 targetNodeId
    expect(sessionStore.getOscilloscopeById('osc1')?.targetNodeId).toBeUndefined();
  });
});

describe('sessionStore validateFreeze 冻结校验', () => {
  function setGraphWith(nodes: Array<Partial<GraphNode>>) {
    sessionStore.setGraph({
      nodes: nodes.map((n, i) => ({
        id: n.id ?? `n${i}`,
        type: n.type ?? 'SOURCE',
        name: n.name ?? `节点${i}`,
        x: 0,
        y: 0,
        params: n.params ?? {},
        deviceId: n.deviceId,
      })) as GraphNode[],
      edges: [],
      frozen: false,
    });
  }

  it('SOURCE 未绑定设备 → valid=false 且报错', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    setGraphWith([{ id: 'src1', type: 'SOURCE', name: '数据源' }]);
    const v = sessionStore.validateFreeze();
    expect(v.valid).toBe(false);
    expect(v.errors.length).toBeGreaterThan(0);
  });

  it('SOURCE 绑定存在的设备（节点 deviceId）→ valid=true', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    setGraphWith([{ id: 'src1', type: 'SOURCE', name: '数据源', deviceId: 'dev1' }]);
    const v = sessionStore.validateFreeze();
    expect(v.valid).toBe(true);
    expect(v.errors).toHaveLength(0);
  });

  it('SOURCE 绑定不存在的设备 → valid=false', () => {
    sessionStore.setDevices([]);
    setGraphWith([{ id: 'src1', type: 'SOURCE', name: '数据源', deviceId: 'ghost' }]);
    const v = sessionStore.validateFreeze();
    expect(v.valid).toBe(false);
    expect(v.errors.some((e) => e.includes('不存在'))).toBe(true);
  });

  it('OUTPUT 未绑定示波器 → 仅警告不判错', () => {
    sessionStore.setDevices([makeDevice('dev1')]);
    setGraphWith([
      { id: 'src1', type: 'SOURCE', name: '数据源', deviceId: 'dev1' },
      { id: 'out1', type: 'OUTPUT', name: '输出' },
    ]);
    const v = sessionStore.validateFreeze();
    expect(v.valid).toBe(true);
    expect(v.warnings.length).toBeGreaterThan(0);
  });
});
