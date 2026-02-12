import type { GraphNode, GraphEdge } from './graph';

// 设备接口
export interface Device {
  id: string;
  name: string;
  status: 'online' | 'offline';
  sampleRate: number;
  channels: number;
  port?: string; // 串口或其他连接信息
}

// 示波器实例接口
export interface Oscilloscope {
  id: string;
  name: string;
  targetNodeId?: string; // 关联的计算图OSC节点ID
  isActive: boolean;
  timeWindow: number; // 时间窗口(秒)
  yScale: number; // Y轴缩放
}

// 计算图配置
export interface GraphConfig {
  nodes: GraphNode[];
  edges: GraphEdge[];
  frozen: boolean;
}

// 节点映射关系
export interface NodeMappings {
  // 输入节点 -> 设备ID
  inputs: Record<string, string>; // nodeId -> deviceId
  // 输出节点 -> 示波器ID
  outputs: Record<string, string>; // nodeId -> oscId
}

// 完整的Session状态
export interface EegSessionState {
  devices: Device[];
  oscilloscopes: Oscilloscope[];
  graph: GraphConfig;
  mappings: NodeMappings;
  lastUpdated: number;
}

const STORAGE_KEY = 'eeg_session_state';

// 默认状态
const defaultState: EegSessionState = {
  devices: [],
  oscilloscopes: [],
  graph: {
    nodes: [],
    edges: [],
    frozen: false,
  },
  mappings: {
    inputs: {},
    outputs: {},
  },
  lastUpdated: Date.now(),
};

class SessionStore {
  private state: EegSessionState;
  private listeners: Set<(state: EegSessionState) => void>;

  constructor() {
    this.state = this.loadFromStorage();
    this.listeners = new Set();
  }

  // 从SessionStorage加载
  private loadFromStorage(): EegSessionState {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        return { ...defaultState, ...JSON.parse(stored) };
      }
    } catch (e) {
      console.error('Failed to load session state:', e);
    }
    return { ...defaultState };
  }

  // 保存到SessionStorage
  private saveToStorage() {
    try {
      this.state.lastUpdated = Date.now();
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
    } catch (e) {
      console.error('Failed to save session state:', e);
    }
  }

  // 通知所有监听器
  private notify() {
    this.listeners.forEach((listener) => listener(this.state));
  }

  // 获取当前状态
  getState(): EegSessionState {
    return { ...this.state };
  }

  // 订阅状态变化
  subscribe(listener: (state: EegSessionState) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  // ========== 设备管理 ==========

  setDevices(devices: Device[]) {
    this.state.devices = devices;
    this.saveToStorage();
    this.notify();
  }

  getDevices(): Device[] {
    return [...this.state.devices];
  }

  getDeviceById(id: string): Device | undefined {
    return this.state.devices.find((d) => d.id === id);
  }

  updateDeviceStatus(id: string, status: Device['status']) {
    const device = this.state.devices.find((d) => d.id === id);
    if (device) {
      device.status = status;
      this.saveToStorage();
      this.notify();
    }
  }

  // ========== 示波器管理 ==========

  setOscilloscopes(oscilloscopes: Oscilloscope[]) {
    this.state.oscilloscopes = oscilloscopes;
    this.saveToStorage();
    this.notify();
  }

  getOscilloscopes(): Oscilloscope[] {
    return [...this.state.oscilloscopes];
  }

  getOscilloscopeById(id: string): Oscilloscope | undefined {
    return this.state.oscilloscopes.find((o) => o.id === id);
  }

  addOscilloscope(osc: Oscilloscope) {
    this.state.oscilloscopes.push(osc);
    this.saveToStorage();
    this.notify();
  }

  removeOscilloscope(id: string) {
    this.state.oscilloscopes = this.state.oscilloscopes.filter((o) => o.id !== id);
    // 清理映射关系
    Object.entries(this.state.mappings.outputs).forEach(([nodeId, oscId]) => {
      if (oscId === id) {
        delete this.state.mappings.outputs[nodeId];
      }
    });
    this.saveToStorage();
    this.notify();
  }

  updateOscilloscope(id: string, updates: Partial<Oscilloscope>) {
    const osc = this.state.oscilloscopes.find((o) => o.id === id);
    if (osc) {
      Object.assign(osc, updates);
      this.saveToStorage();
      this.notify();
    }
  }

  // ========== 计算图管理 ==========

  setGraph(graph: GraphConfig) {
    this.state.graph = graph;
    this.saveToStorage();
    this.notify();
  }

  getGraph(): GraphConfig {
    return {
      nodes: [...this.state.graph.nodes],
      edges: [...this.state.graph.edges],
      frozen: this.state.graph.frozen,
    };
  }

  // ========== 节点映射管理 ==========

  // 绑定输入节点到设备
  bindInputNode(nodeId: string, deviceId: string): boolean {
    const device = this.getDeviceById(deviceId);
    if (!device) {
      console.warn(`Device ${deviceId} not found`);
      return false;
    }
    this.state.mappings.inputs[nodeId] = deviceId;
    this.saveToStorage();
    this.notify();
    return true;
  }

  // 解绑输入节点
  unbindInputNode(nodeId: string) {
    delete this.state.mappings.inputs[nodeId];
    this.saveToStorage();
    this.notify();
  }

  // 获取输入节点绑定的设备
  getInputNodeDevice(nodeId: string): Device | undefined {
    const deviceId = this.state.mappings.inputs[nodeId];
    return deviceId ? this.getDeviceById(deviceId) : undefined;
  }

  // 绑定输出节点到示波器
  bindOutputNode(nodeId: string, oscId: string): boolean {
    const osc = this.getOscilloscopeById(oscId);
    if (!osc) {
      console.warn(`Oscilloscope ${oscId} not found`);
      return false;
    }
    this.state.mappings.outputs[nodeId] = oscId;
    // 更新示波器的targetNodeId
    osc.targetNodeId = nodeId;
    this.saveToStorage();
    this.notify();
    return true;
  }

  // 解绑输出节点
  unbindOutputNode(nodeId: string) {
    const oscId = this.state.mappings.outputs[nodeId];
    if (oscId) {
      const osc = this.getOscilloscopeById(oscId);
      if (osc) {
        osc.targetNodeId = undefined;
      }
    }
    delete this.state.mappings.outputs[nodeId];
    this.saveToStorage();
    this.notify();
  }

  // 获取输出节点绑定的示波器
  getOutputNodeOscilloscope(nodeId: string): Oscilloscope | undefined {
    const oscId = this.state.mappings.outputs[nodeId];
    return oscId ? this.getOscilloscopeById(oscId) : undefined;
  }

  // 获取所有输入节点映射
  getInputMappings(): Record<string, string> {
    return { ...this.state.mappings.inputs };
  }

  // 获取所有输出节点映射
  getOutputMappings(): Record<string, string> {
    return { ...this.state.mappings.outputs };
  }

  // ========== 冻结验证 ==========

  // 验证是否可以冻结
  validateFreeze(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    // 检查所有SOURCE节点是否已绑定设备
    const sourceNodes = this.state.graph.nodes.filter((n) => n.type === 'SOURCE');
    sourceNodes.forEach((node) => {
      if (!this.state.mappings.inputs[node.id]) {
        errors.push(`输入节点 "${node.name}" 未绑定设备`);
      }
    });

    // 检查所有OSC节点是否已绑定示波器
    const oscNodes = this.state.graph.nodes.filter((n) => n.type === 'OSC');
    oscNodes.forEach((node) => {
      if (!this.state.mappings.outputs[node.id]) {
        errors.push(`示波器节点 "${node.name}" 未绑定显示通道`);
      }
    });

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  // ========== 工具方法 ==========

  // 清空所有状态
  clear() {
    this.state = { ...defaultState };
    this.saveToStorage();
    this.notify();
  }

  // 导出完整状态（用于调试）
  exportState(): string {
    return JSON.stringify(this.state, null, 2);
  }

  // 导入状态
  importState(json: string) {
    try {
      const parsed = JSON.parse(json);
      this.state = { ...defaultState, ...parsed };
      this.saveToStorage();
      this.notify();
      return true;
    } catch (e) {
      console.error('Failed to import state:', e);
      return false;
    }
  }
}

// 单例导出
export const sessionStore = new SessionStore();

// 用于React/Vue的Hook辅助函数
export function useSessionStore() {
  return sessionStore;
}
