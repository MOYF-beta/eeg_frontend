import { ref, computed } from 'vue';
import { eegWebSocket, type EegDataPacket } from './websocket';
import { controlWebSocket, type ControlState } from './controlWebSocket';

// EEG 数据包类型（兼容旧接口）
export interface EegPacket {
  t: number; // 时间戳（秒）
  channels: number[]; // 各通道数值
}

// 计算图运行状态接口
export interface GraphRuntimeState {
  isRunning: boolean;
  runtimeMode: 'live' | 'offline';
  frozen: boolean;
  offlineProgress: number;
  processingDelayMs: number;
  nonRealtime: boolean;
  runtimeWarning: string | null;
  canEditGraph: boolean;
  canRunGraph: boolean;
  statusDescription: string;
}

// 默认状态
const defaultState: GraphRuntimeState = {
  isRunning: false,
  runtimeMode: 'live',
  frozen: false,
  offlineProgress: 0,
  processingDelayMs: 0,
  nonRealtime: false,
  runtimeWarning: null,
  canEditGraph: true,
  canRunGraph: false,
  statusDescription: '编辑中 - 可编辑设备和计算图'
};

// 全局状态
const state = ref<GraphRuntimeState>({ ...defaultState });

// 计算属性
const isRunning = computed(() => state.value.isRunning);
const runtimeMode = computed(() => state.value.runtimeMode);
const frozen = computed(() => state.value.frozen);
const offlineProgress = computed(() => state.value.offlineProgress);
const processingDelayMs = computed(() => state.value.processingDelayMs);
const nonRealtime = computed(() => state.value.nonRealtime);
const runtimeWarning = computed(() => state.value.runtimeWarning);
const canEditGraph = computed(() => state.value.canEditGraph);
const canRunGraph = computed(() => state.value.canRunGraph);
const statusDescription = computed(() => state.value.statusDescription);

// 更新状态
function updateState(newState: Partial<GraphRuntimeState>) {
  const isRunning = newState.isRunning !== undefined ? newState.isRunning : state.value.isRunning;

  state.value = {
    ...state.value,
    ...newState,
    // 重新计算依赖状态
    canEditGraph: !isRunning,  // 未运行时可以编辑
    canRunGraph: !isRunning,   // 未运行时可以运行
    statusDescription: getStatusDescription(isRunning)
  };
}

// 获取状态描述
function getStatusDescription(isRunning: boolean): string {
  if (isRunning) {
    return '运行中 - 禁止修改设备和计算图';
  } else {
    return '编辑中 - 可编辑设备和计算图';
  }
}

// 从控制 WS 状态推送更新本地状态
function applyControlState(cs: ControlState) {
  const rt = cs.runtime;
  // frozen 权威来源是 graph.frozen（后端 _RUNTIME_STATE 不含 frozen 字段），
  // runtime.frozen 仅作向后兼容回退。
  const frozenVal = cs.graph?.frozen ?? rt.frozen ?? false;
  updateState({
    isRunning: rt.running,
    runtimeMode: (rt.mode || 'live') as 'live' | 'offline',
    offlineProgress: Number(rt.progress || 0),
    processingDelayMs: Number(rt.processingDelayMs || 0),
    nonRealtime: Boolean(rt.nonRealtime),
    runtimeWarning: rt.warning ? String(rt.warning) : null,
    frozen: Boolean(frozenVal),
  });

  // 运行中确保数据 WS 已连接
  if (rt.running && !eegWebSocket.isConnected()) {
    eegWebSocket.connect();
  }
}

// 运行计算图（通过控制 WS）。运行时后端自动锁定图（running 标志拒绝 set_graph），
// 不再需要先冻结——冻结是已退出 UI 的历史遗留概念。
function runByMode(mode: 'live' | 'offline') {
  controlWebSocket.run(mode);
}

// 停止运行（通过控制 WS）。停止后画布自动恢复可编辑。
function stopRun() {
  controlWebSocket.stop();
}

// 兼容旧接口：冻结已退出 UI，保留为透传以免破坏旧调用方/e2e，新代码不应使用。
function setFreeze(frozenVal: boolean) {
  controlWebSocket.freeze(frozenVal);
}

// 兼容：保留 pollRuntimeState 但不再实际轮询
async function pollRuntimeState() {
  // 控制 WS 自动推送，此处无需操作
}

// 初始化：连接控制 WS 并订阅状态
let _initialized = false;
function init() {
  if (_initialized) return;
  _initialized = true;
  controlWebSocket.connect();
  controlWebSocket.onState(applyControlState);
}

// 清理
function cleanup() {
  controlWebSocket.disconnect();
  _initialized = false;
}

// 兼容旧接口
const startPolling = init;
const stopPolling = cleanup;

// ========== 数据流转发（从 runtime.ts 合并）==========

// 数据包订阅者回调
const packetSubscribers: ((packet: EegPacket) => void)[] = [];

// WebSocket 数据转发：EegDataPacket → EegPacket
eegWebSocket.onData((packet: EegDataPacket) => {
  const eegPacket: EegPacket = {
    t: packet.timestamp / 1000,
    channels: packet.channels,
  };
  packetSubscribers.forEach((cb) => cb(eegPacket));
});

// 订阅数据流（示波器调用）
function subscribeData(callback: (packet: EegPacket) => void) {
  packetSubscribers.push(callback);
  return () => {
    const index = packetSubscribers.indexOf(callback);
    if (index > -1) packetSubscribers.splice(index, 1);
  };
}

// 导出
export const graphRuntimeStore = {
  // 状态
  state,
  
  // 计算属性
  isRunning,
  runtimeMode,
  frozen,
  offlineProgress,
  processingDelayMs,
  nonRealtime,
  runtimeWarning,
  canEditGraph,
  canRunGraph,
  statusDescription,
  
  // 方法
  updateState,
  pollRuntimeState,
  startPolling,
  stopPolling,
  runByMode,
  stopRun,
  setFreeze,
  init,
  cleanup,

  // 数据流
  subscribeData,
};

// 默认导出
export default graphRuntimeStore;