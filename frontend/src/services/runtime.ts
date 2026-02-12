import { reactive, readonly } from 'vue';

// EEG 数据包类型
export interface EegPacket {
  t: number;  // 时间戳
  channels: number[];  // 各通道数值
}

// 计算图运行状态
interface GraphRuntimeState {
  isRunning: boolean;
  activeOscNodes: string[];  // 当前活动的示波器节点ID
  lastPacket: EegPacket | null;
}

// 创建响应式状态
const state = reactive<GraphRuntimeState>({
  isRunning: false,
  activeOscNodes: [],
  lastPacket: null,
});

// 订阅者回调
const subscribers: ((packet: EegPacket) => void)[] = [];

export const graphRuntime = {
  // 获取只读状态
  state: readonly(state),

  // 开始运行
  start(nodeIds: string[]) {
    state.isRunning = true;
    state.activeOscNodes = nodeIds;
  },

  // 停止运行
  stop() {
    state.isRunning = false;
    state.activeOscNodes = [];
    state.lastPacket = null;
  },

  // 发送数据包（从计算图到示波器）
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
};
