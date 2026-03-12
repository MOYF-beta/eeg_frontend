import { ref, computed } from 'vue';
import { getGraphRuntimeState, runGraph, stopGraph, setGraphFrozen } from './graph';
import { eegWebSocket } from './websocket';

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

// 轮询定时器
let pollingTimer: number | null = null;

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
  const frozen = newState.frozen !== undefined ? newState.frozen : state.value.frozen;
  const isRunning = newState.isRunning !== undefined ? newState.isRunning : state.value.isRunning;
  
  state.value = {
    ...state.value,
    ...newState,
    // 重新计算依赖状态
    canEditGraph: !isRunning,  // 未运行时可以编辑
    canRunGraph: !isRunning,   // 未运行时可以运行
    statusDescription: getStatusDescription(isRunning, frozen)
  };
}

// 获取状态描述
function getStatusDescription(isRunning: boolean, frozen: boolean): string {
  if (isRunning) {
    return '运行中 - 禁止修改设备和计算图';
  } else {
    return '编辑中 - 可编辑设备和计算图';
  }
}

// 轮询运行时状态
async function pollRuntimeState() {
  try {
    const res = await getGraphRuntimeState();
    if (res.ok) {
      const wasRunning = state.value.isRunning;
      const newState = {
        isRunning: res.state.running,
        runtimeMode: (res.state.mode || 'live') as 'live' | 'offline',
        offlineProgress: Number(res.state.progress || 0),
        processingDelayMs: Number(res.state.processingDelayMs || 0),
        nonRealtime: Boolean(res.state.nonRealtime),
        runtimeWarning: res.state.warning ? String(res.state.warning) : null,
        frozen: Boolean(res.state.frozen ?? false)  // 使用后端返回的frozen状态
      };
      
      // 记录状态变化
      if (newState.isRunning !== state.value.isRunning) {
        console.log(`[GraphRuntimeStore] Runtime state changed: isRunning=${newState.isRunning}, mode=${newState.runtimeMode}`);
      }
      
      updateState(newState);
      
      // 如果计算图开始运行，确保WebSocket已连接
      if (newState.isRunning && !eegWebSocket.isConnected()) {
        console.log('[GraphRuntimeStore] Graph is running but WebSocket not connected, connecting...');
        eegWebSocket.connect();
      }
      
      // 如果计算图停止运行，更新WebSocket订阅
      if (wasRunning && !newState.isRunning) {
        console.log('[GraphRuntimeStore] Graph stopped, updating WebSocket subscription');
        eegWebSocket.updateSubscription();
      }
    } else {
      console.warn('[GraphRuntimeStore] Failed to get runtime state:', res);
    }
  } catch (e) {
    console.error('[GraphRuntimeStore] Failed to poll runtime state:', e);
  }
}

// 开始轮询
function startPolling() {
  if (pollingTimer) return;
  pollRuntimeState();
  pollingTimer = window.setInterval(pollRuntimeState, 2000);
}

// 停止轮询
function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
}

// 运行计算图
async function runByMode(mode: 'live' | 'offline') {
  try {
    // 运行时自动冻结计算图
    if (!state.value.frozen) {
      await setGraphFrozen(true);
      updateState({
        frozen: true
      });
    }
    
    await runGraph(mode);
    updateState({
      isRunning: true,
      runtimeMode: mode
    });
    startPolling();
  } catch (err) {
    console.error('[GraphRuntimeStore] Failed to run graph:', err);
    throw err;
  }
}

// 停止运行
async function stopRun() {
  try {
    await stopGraph();
    
    // 停止时自动解冻计算图
    if (state.value.frozen) {
      await setGraphFrozen(false);
      updateState({
        frozen: false
      });
    }
    
    updateState({
      isRunning: false,
      offlineProgress: 0,
      processingDelayMs: 0,
      nonRealtime: false,
      runtimeWarning: null
    });
    stopPolling();
  } catch (err) {
    console.error('[GraphRuntimeStore] Failed to stop graph:', err);
    throw err;
  }
}

// 设置冻结状态
async function setFreeze(frozen: boolean) {
  try {
    await setGraphFrozen(frozen);
    updateState({
      frozen
    });
  } catch (err) {
    console.error('[GraphRuntimeStore] Failed to set freeze:', err);
    throw err;
  }
}

// 初始化
function init() {
  // 开始轮询状态
  startPolling();
}

// 清理
function cleanup() {
  stopPolling();
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
  cleanup
};

// 默认导出
export default graphRuntimeStore;