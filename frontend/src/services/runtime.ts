/**
 * runtime.ts — 已合并到 graphRuntimeStore。
 *
 * @deprecated 此文件保留为兼容层。新代码请直接使用 graphRuntimeStore。
 * 计划移除时间：下一个大版本。
 */

import { sessionStore } from './sessionStore';
import { eegWebSocket } from './websocket';
import { graphRuntimeStore, type EegPacket } from './graphRuntimeStore';

export type { EegPacket };

export const graphRuntime = {
  /** 旧版 state 代理（映射到 graphRuntimeStore 的计算属性） */
  state: {
    get isRunning() { return graphRuntimeStore.isRunning.value; },
    get error() { return graphRuntimeStore.runtimeWarning.value; },
    get wsStatus() {
      return eegWebSocket.getStatus() as 'disconnected' | 'connecting' | 'connected' | 'error';
    },
  },

  /** 开始运行（旧版接口：冻结 + 连接 WS） */
  async start(_nodeIds?: string[]) {
    try {
      await graphRuntimeStore.runByMode('live');
      return true;
    } catch {
      return false;
    }
  },

  /** 停止运行（旧版接口：解冻 + 断开 WS） */
  stop() {
    graphRuntimeStore.stopRun();
  },

  /** 订阅数据流 */
  subscribe(callback: (packet: EegPacket) => void) {
    return graphRuntimeStore.subscribeData(callback);
  },

  /** 检查节点是否是活动的 OSC 节点 */
  isActiveOscNode(_nodeId: string): boolean {
    return graphRuntimeStore.isRunning.value;
  },

  /** 获取节点的映射信息 */
  getNodeMapping(nodeId: string): { deviceId?: string; oscId?: string } {
    return {
      deviceId: sessionStore.getInputMappings()[nodeId],
      oscId: sessionStore.getOutputMappings()[nodeId],
    };
  },

  /** 清理资源 */
  dispose() {
    // 现在由 graphRuntimeStore.cleanup() 管理
  },
};
