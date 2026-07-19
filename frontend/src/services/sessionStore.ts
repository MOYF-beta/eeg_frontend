import type { GraphNode, GraphEdge } from './graph';
import { deviceApi } from './deviceApi';

// 信号类型枚举
export type SignalType = 'sine' | 'square' | 'triangle' | 'pulse' | 'multi_sine';

// 噪声类型枚举
export type NoiseType = 'none' | 'white' | 'pink' | 'brownian' | 'gaussian';

// 信号配置接口
export interface SignalConfig {
  type: SignalType;
  frequency: number; // 频率 (Hz)
  amplitude: number; // 幅度
  phase?: number; // 相位 (弧度)
  dutyCycle?: number; // 占空比 (0-1，用于方波和脉冲)
  pulseWidth?: number; // 脉冲宽度 (秒，用于脉冲)
  sineComponents?: { // 多个正弦波叠加配置
    frequency: number;
    amplitude: number;
    phase: number;
  }[];
}

// 噪声配置接口
export interface NoiseConfig {
  type: NoiseType;
  amplitude: number; // 噪声幅度
  seed?: number; // 随机种子
  cutoffFrequency?: number; // 截止频率 (Hz)
}

// 通道配置接口
export interface ChannelConfig {
  index: number;
  signal: SignalConfig;
  noise?: NoiseConfig;
  enabled: boolean;
}

// 模拟设备配置接口
export interface SimulatedDeviceConfig {
  channels: ChannelConfig[];
  globalNoise?: NoiseConfig; // 全局噪声
}

// 设备接口
export interface Device {
  id: string;
  name: string;
  status: 'online' | 'offline';
  samplingRate: number;
  channelCount: number;
  type: 'simulated' | 'real';
  config: {
    port?: string;
    baudrate?: number;
    connected?: boolean;
    acquiring?: boolean;
    description?: string;
    manufacturer?: string;
    product?: string;
    hwid?: string;
    is_ch340?: boolean;
    vid?: string | number;
    pid?: string | number;
    channels?: Array<{
      index: number;
      wave_type: string;
      frequency: number;
      amplitude: number;
      alias: string;
      noise_type?: string;
      noise_amplitude?: number;
      duty_cycle?: number;
    }>;
  };
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
  // 示波器视图到节点的映射（视图选择 -> 节点状态显示）
  viewBindings: Record<string, string>; // viewId -> nodeId
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

// 运行时状态快照
export interface RuntimeState {
  running: boolean;
  mode: 'live' | 'offline';
  progress: number | null;
  processingDelayMs: number;
  nonRealtime: boolean;
  warning: string | null;
}

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
    viewBindings: {},
  },
  lastUpdated: Date.now(),
};

class SessionStore {
  private state: EegSessionState;
  private listeners: Set<(state: EegSessionState) => void>;

  // 全局轮询控制
  private _pollTimer: number | null = null;
  private _pollInterval = 0;
  public runtime: RuntimeState = {
    running: false, mode: 'live', progress: null,
    processingDelayMs: 0, nonRealtime: false, warning: null,
  };

  constructor() {
    this.state = this.loadFromStorage();
    this.listeners = new Set();
  }

  // 从localStorage加载
  private loadFromStorage(): EegSessionState {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // 确保嵌套对象有默认值
        return {
          ...defaultState,
          ...parsed,
          mappings: {
            ...defaultState.mappings,
            ...(parsed.mappings || {}),
          },
          graph: {
            ...defaultState.graph,
            ...(parsed.graph || {}),
          },
        };
      }
    } catch (e) {
      console.error('Failed to load session state:', e);
    }
    return { ...defaultState };
  }

  // 保存到localStorage
  private saveToStorage() {
    try {
      this.state.lastUpdated = Date.now();
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
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

  /**
   * 从后端API加载设备列表
   */
  async loadDevicesFromBackend(): Promise<void> {
    try {
      const devices = await deviceApi.getDevices();
      this.setDevices(devices);
    } catch (error) {
      console.error('Failed to load devices from backend:', error);
      // 保持现有设备列表
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

  // ========== 示波器视图绑定（单向：视图选择 -> 节点状态）==========

  // 绑定示波器视图到节点
  bindViewToNode(viewId: string, nodeId: string | null) {
    if (!this.state.mappings.viewBindings) {
      this.state.mappings.viewBindings = {};
    }
    if (nodeId) {
      this.state.mappings.viewBindings[viewId] = nodeId;
    } else {
      // 查找并删除此视图的所有绑定
      Object.keys(this.state.mappings.viewBindings).forEach(key => {
        if (key === viewId) {
          delete this.state.mappings.viewBindings[key];
        }
      });
    }
    this.saveToStorage();
    this.notify();
  }

  // 获取视图绑定的节点
  getViewBoundNode(viewId: string): string | undefined {
    return this.state.mappings?.viewBindings?.[viewId];
  }

  // 获取节点被哪些视图绑定
  getNodeBoundViews(nodeId: string): string[] {
    const bindings = this.state.mappings?.viewBindings || {};
    return Object.entries(bindings)
      .filter(([, boundNodeId]) => boundNodeId === nodeId)
      .map(([viewId]) => viewId);
  }

  // 获取所有视图绑定
  getViewBindings(): Record<string, string> {
    return { ...(this.state.mappings?.viewBindings || {}) };
  }

  // 检查节点是否被任何视图绑定
  isNodeBoundByView(nodeId: string): boolean {
    const bindings = this.state.mappings?.viewBindings || {};
    return Object.values(bindings).includes(nodeId);
  }

  // ========== 冻结验证 ==========

  // 验证是否可以冻结
  validateFreeze(): { valid: boolean; errors: string[]; warnings: string[] } {
    const errors: string[] = [];
    const warnings: string[] = [];

    // 检查所有SOURCE节点是否已绑定设备（从节点数据读取）
    const sourceNodes = this.state.graph.nodes.filter((n) => n.type === 'SOURCE');
    sourceNodes.forEach((node) => {
      const deviceId = node.deviceId || node.params?.deviceId;
      if (!deviceId) {
        errors.push(`输入节点 "${node.name}" 未绑定设备`);
      } else {
        // 检查设备是否存在
        const device = this.getDeviceById(deviceId as string);
        if (!device) {
          errors.push(`输入节点 "${node.name}" 绑定的设备不存在: ${deviceId}`);
        }
      }
    });

    // 检查输出节点是否绑定示波器（改为警告，不是错误）
    const oscNodes = this.state.graph.nodes.filter((n) => n.type === 'OUTPUT');
    oscNodes.forEach((node) => {
      if (!this.state.mappings.outputs[node.id]) {
        warnings.push(`输出节点 "${node.name}" 未绑定到显示实例，冻结后可在可视化页面绑定`);
      }
    });

    return {
      valid: errors.length === 0,
      errors,
      warnings,
    };
  }

  // ========== 工具方法 ==========

  // ========== 控制通道（替代轮询）==========

  startGlobalPolling() {
    // 不再 setInterval 轮询，改为通过 controlWebSocket 订阅状态推送
    // 首次仍需 fetch 一次图结构（控制 WS 可能还未连接）
    this._initialFetch();
  }

  private async _initialFetch() {
    try {
      const graphRes = await fetch('/api/graph/');
      if (graphRes.ok) {
        const graphData = await graphRes.json();
        if (Array.isArray(graphData.nodes) && Array.isArray(graphData.edges)) {
          this.state.graph.nodes = graphData.nodes;
          this.state.graph.edges = graphData.edges;
          this.state.graph.frozen = Boolean(graphData.frozen);
          this.saveToStorage();
          this.notify();
        }
      }
    } catch (e) {
      console.warn('[SessionStore] Initial graph fetch failed:', e);
    }
  }

  stopGlobalPolling() {
    // 控制 WS 接管，无需清理计时器
  }

  private async _pollTick() {
    // 兼容保留：控制 WS 已接管图同步，此方法不再被定时调用
  }

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

  // ========== 状态权限检查 ==========

  // 检查是否允许编辑计算图
  canEditGraph(): boolean {
    // 根据新的设计，未运行时可以编辑计算图
    // 运行状态由graphRuntimeStore管理，这里返回true让graphRuntimeStore控制
    return true;
  }

  // 检查是否允许编辑设备（冻结时允许，运行时禁止）
  canEditDevices(isRunning: boolean = false): boolean {
    // 如果正在运行，禁止编辑设备
    if (isRunning) {
      return false;
    }
    // 冻结状态允许编辑设备
    return true;
  }

  // 检查是否允许运行计算图（冻结已退出 UI，运行不再要求冻结，由 isRunning 在外层判定）
  canRunGraph(): boolean {
    return true;
  }

  // 获取当前状态描述
  getStatusDescription(isRunning: boolean = false): string {
    if (isRunning) {
      return '运行中 - 禁止修改设备和计算图';
    } else {
      return '编辑中 - 可编辑设备和计算图';
    }
  }

  // 设置计算图冻结状态（内部使用，外部通过API调用）
  setGraphFrozenInternal(frozen: boolean) {
    this.state.graph.frozen = frozen;
    this.saveToStorage();
    this.notify();
  }
}

// 单例导出
export const sessionStore = new SessionStore();

// 用于React/Vue的Hook辅助函数
export function useSessionStore() {
  return sessionStore;
}
