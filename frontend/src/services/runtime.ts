import { reactive, readonly } from 'vue';
import { sessionStore } from './sessionStore';
import { eegWebSocket, type EegDataPacket } from './websocket';

// EEG 数据包类型（兼容旧接口）
export interface EegPacket {
  t: number; // 时间戳
  channels: number[]; // 各通道数值
}

// 计算图运行状态
interface GraphRuntimeState {
  isRunning: boolean;
  activeOscNodes: string[]; // 当前活动的示波器节点ID
  lastPacket: EegPacket | null;
  wsStatus: 'disconnected' | 'connecting' | 'connected' | 'error';
  error: string | null;
}

// 创建响应式状态
const state = reactive<GraphRuntimeState>({
  isRunning: false,
  activeOscNodes: [],
  lastPacket: null,
  wsStatus: 'disconnected',
  error: null,
});

// 订阅者回调
const subscribers: ((packet: EegPacket) => void)[] = [];

// WebSocket数据转发
const wsUnsubscribe = eegWebSocket.onData((packet: EegDataPacket) => {
  // 转换为旧格式
  const eegPacket: EegPacket = {
    t: packet.timestamp / 1000, // 转换为秒
    channels: packet.channels,
  };

  state.lastPacket = eegPacket;
  subscribers.forEach((cb) => cb(eegPacket));
});

// WebSocket状态监听
const wsStatusUnsubscribe = eegWebSocket.onStatusChange((status) => {
  state.wsStatus = status;
});

// WebSocket错误监听
const wsErrorUnsubscribe = eegWebSocket.onError(() => {
  state.error = 'WebSocket连接错误';
});

export const graphRuntime = {
  // 获取只读状态
  state: readonly(state),

  // 开始运行（冻结计算图后调用）
  async start(nodeIds?: string[]) {
    // 验证是否可以冻结
    const validation = sessionStore.validateFreeze();
    if (!validation.valid) {
      state.error = validation.errors.join('; ');
      console.error('Cannot start:', validation.errors);
      return false;
    }

    state.error = null;

    // 如果没有传入nodeIds，从SessionStorage获取
    if (!nodeIds) {
      const graph = sessionStore.getGraph();
      nodeIds = graph.nodes.filter((n) => n.type === 'OSC').map((n) => n.id);
    }

    state.activeOscNodes = nodeIds;
    state.isRunning = true;

    // 连接WebSocket
    eegWebSocket.connect();

    return true;
  },

  // 停止运行（解冻计算图后调用）
  stop() {
    state.isRunning = false;
    state.activeOscNodes = [];
    state.lastPacket = null;
    state.error = null;

    // 断开WebSocket
    eegWebSocket.disconnect();
  },

  // 发送数据包（从计算图到示波器）- 用于Mock测试
  emitPacket(packet: EegPacket) {
    if (!state.isRunning) return;
    state.lastPacket = packet;
    subscribers.forEach((cb) => cb(packet));
  },

  // 订阅数据（示波器调用）
  subscribe(callback: (packet: EegPacket) => void) {
    subscribers.push(callback);
    return () => {
      const index = subscribers.indexOf(callback);
      if (index > -1) subscribers.splice(index, 1);
    };
  },

  // 检查节点是否是活动的OSC节点
  isActiveOscNode(nodeId: string): boolean {
    return state.activeOscNodes.includes(nodeId);
  },

  // 获取节点的映射信息
  getNodeMapping(nodeId: string): { deviceId?: string; oscId?: string } {
    return {
      deviceId: sessionStore.getInputMappings()[nodeId],
      oscId: sessionStore.getOutputMappings()[nodeId],
    };
  },

  // 清理资源（应用卸载时调用）
  dispose() {
    wsUnsubscribe();
    wsStatusUnsubscribe();
    wsErrorUnsubscribe();
    this.stop();
  },
};
