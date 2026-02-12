import { sessionStore } from './sessionStore';

// WebSocket连接状态
type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// 数据包接口
export interface EegDataPacket {
  timestamp: number;
  nodeId: string; // 数据来源节点ID
  channels: number[]; // 各通道数据值
  sampleRate?: number;
}

// WebSocket配置
interface WsConfig {
  url: string;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
}

const defaultConfig: WsConfig = {
  url: `ws://${window.location.hostname}:8000/ws/eeg/`,
  reconnectInterval: 3000,
  maxReconnectAttempts: 5,
  heartbeatInterval: 30000,
};

class EegWebSocket {
  private ws: WebSocket | null = null;
  private status: WsStatus = 'disconnected';
  private config: WsConfig;
  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private listeners: {
    onData: Set<(packet: EegDataPacket) => void>;
    onStatusChange: Set<(status: WsStatus) => void>;
    onError: Set<(error: Event) => void>;
  };

  constructor(config: Partial<WsConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
    this.listeners = {
      onData: new Set(),
      onStatusChange: new Set(),
      onError: new Set(),
    };
  }

  // ========== 连接管理 ==========

  connect() {
    if (this.ws?.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connecting...');
      return;
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected');
      return;
    }

    this.setStatus('connecting');
    console.log('Connecting to WebSocket:', this.config.url);

    try {
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        console.log('WebSocket connected');
        this.setStatus('connected');
        this.reconnectAttempts = 0;
        this.startHeartbeat();

        // 发送订阅消息，告诉后端我们需要哪些节点的数据
        this.subscribeToNodes();
      };

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data);
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.setStatus('error');
        this.listeners.onError.forEach((cb) => cb(error));
      };

      this.ws.onclose = () => {
        console.log('WebSocket closed');
        this.setStatus('disconnected');
        this.stopHeartbeat();
        this.attemptReconnect();
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.setStatus('error');
      this.attemptReconnect();
    }
  }

  disconnect() {
    console.log('Disconnecting WebSocket...');
    this.stopReconnect();
    this.stopHeartbeat();

    if (this.ws) {
      // 发送取消订阅消息
      this.unsubscribeFromNodes();

      this.ws.close();
      this.ws = null;
    }

    this.setStatus('disconnected');
  }

  // ========== 重连机制 ==========

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;
    console.log(
      `Reconnecting... Attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts}`
    );

    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, this.config.reconnectInterval);
  }

  private stopReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }

  // ========== 心跳机制 ==========

  private startHeartbeat() {
    this.heartbeatTimer = window.setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, this.config.heartbeatInterval);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  // ========== 消息处理 ==========

  private handleMessage(data: string) {
    try {
      const message = JSON.parse(data);

      // 处理心跳响应
      if (message.type === 'pong') {
        return;
      }

      // 处理数据包
      if (message.type === 'data') {
        const packet: EegDataPacket = {
          timestamp: message.timestamp || Date.now(),
          nodeId: message.nodeId,
          channels: message.channels,
          sampleRate: message.sampleRate,
        };
        this.listeners.onData.forEach((cb) => cb(packet));
      }

      // 处理错误消息
      if (message.type === 'error') {
        console.error('Server error:', message.error);
      }
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e);
    }
  }

  // ========== 订阅管理 ==========

  private subscribeToNodes() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    // 获取所有需要订阅的OSC节点ID
    const mappings = sessionStore.getOutputMappings();
    const nodeIds = Object.keys(mappings);

    if (nodeIds.length > 0) {
      this.ws.send(
        JSON.stringify({
          type: 'subscribe',
          nodeIds: nodeIds,
        })
      );
      console.log('Subscribed to nodes:', nodeIds);
    }
  }

  private unsubscribeFromNodes() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    this.ws.send(
      JSON.stringify({
        type: 'unsubscribe',
      })
    );
    console.log('Unsubscribed from all nodes');
  }

  // 动态更新订阅（当计算图变化时调用）
  updateSubscription() {
    if (this.status === 'connected') {
      this.subscribeToNodes();
    }
  }

  // ========== 事件监听 ==========

  onData(callback: (packet: EegDataPacket) => void): () => void {
    this.listeners.onData.add(callback);
    return () => this.listeners.onData.delete(callback);
  }

  onStatusChange(callback: (status: WsStatus) => void): () => void {
    this.listeners.onStatusChange.add(callback);
    return () => this.listeners.onStatusChange.delete(callback);
  }

  onError(callback: (error: Event) => void): () => void {
    this.listeners.onError.add(callback);
    return () => this.listeners.onError.delete(callback);
  }

  // ========== 状态获取 ==========

  getStatus(): WsStatus {
    return this.status;
  }

  isConnected(): boolean {
    return this.status === 'connected';
  }

  private setStatus(status: WsStatus) {
    this.status = status;
    this.listeners.onStatusChange.forEach((cb) => cb(status));
  }

  // ========== 发送命令 ==========

  // 发送控制命令到后端
  sendCommand(command: string, params?: Record<string, unknown>) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected');
      return false;
    }

    this.ws.send(
      JSON.stringify({
        type: 'command',
        command,
        params,
      })
    );
    return true;
  }
}

// 单例导出
export const eegWebSocket = new EegWebSocket();

// 用于React/Vue的Hook辅助函数
export function useEegWebSocket() {
  return eegWebSocket;
}
