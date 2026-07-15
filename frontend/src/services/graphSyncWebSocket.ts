/**
 * graphSyncWebSocket — 已重构为 controlWebSocket 的代理。
 *
 * 不再打开独立的 ws/graph-sync/ 连接。
 * 从 controlWebSocket 的 state 推送中提取 graph 字段，
 * 以 GraphSyncMessage 格式转发给 onGraph 监听器。
 *
 * GraphEditor.vue 的 onGraph 回调接口保持不变。
 */

import type { GraphPayload } from './graph';
import { controlWebSocket } from './controlWebSocket';

type SyncStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface GraphSyncMessage {
  graph: GraphPayload;
  reason?: string;
  timestamp?: number;
}

class GraphSyncWebSocketProxy {
  private status: SyncStatus = 'disconnected';
  private listeners = {
    onGraph: new Set<(message: GraphSyncMessage) => void>(),
    onStatus: new Set<(status: SyncStatus) => void>(),
  };
  private unsubState: (() => void) | null = null;
  private unsubStatus: (() => void) | null = null;
  private _connected = false;

  connect() {
    if (this._connected) return;
    this._connected = true;

    // 确保底层 controlWebSocket 已连接
    if (!controlWebSocket.isConnected()) {
      controlWebSocket.connect();
    }

    this.setStatus('connected');

    // 订阅控制状态，提取 graph 部分转发
    this.unsubState = controlWebSocket.onState((cs) => {
      const msg: GraphSyncMessage = {
        graph: cs.graph,
        reason: cs.reason || 'synced',
        timestamp: Date.now(),
      };
      this.listeners.onGraph.forEach((cb) => cb(msg));
    });

    // 代理连接状态
    this.unsubStatus = controlWebSocket.onStatus((s) => {
      this.setStatus(s);
    });
  }

  disconnect() {
    this._connected = false;
    if (this.unsubState) {
      this.unsubState();
      this.unsubState = null;
    }
    if (this.unsubStatus) {
      this.unsubStatus();
      this.unsubStatus = null;
    }
    this.setStatus('disconnected');
  }

  onGraph(callback: (message: GraphSyncMessage) => void): () => void {
    this.listeners.onGraph.add(callback);
    return () => this.listeners.onGraph.delete(callback);
  }

  onStatus(callback: (status: SyncStatus) => void): () => void {
    this.listeners.onStatus.add(callback);
    return () => this.listeners.onStatus.delete(callback);
  }

  private setStatus(status: SyncStatus) {
    this.status = status;
    this.listeners.onStatus.forEach((cb) => cb(status));
  }
}

export const graphSyncWebSocket = new GraphSyncWebSocketProxy();
