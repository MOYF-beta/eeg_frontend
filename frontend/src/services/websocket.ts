
// WebSocket连接状态
type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

// 数据包接口
export interface EegDataPacket {
  timestamp: number;
  utcFirstFrameMs?: number;
  nodeId: string; // 数据来源节点ID
  nodeType?: string;
  channels: number[]; // 各通道数据值
  channelNames?: string[];
  samples?: number[][]; // 批量样本（可选）
  sampleRate?: number;
  fftSize?: number;
  freqResolution?: number;
  spectra?: number[][]; // 每通道频谱
  spectrum?: number[]; // 平均频谱
  spectrogramRow?: number[]; // 时频谱单帧(0~1)
  spectrogramDbMin?: number;
  spectrogramDbMax?: number;
  processingDelayMs?: number;
  runtimeMode?: 'live' | 'offline';
  nonRealtime?: boolean;
  performanceWarning?: string | null;
}

// WebSocket配置
interface WsConfig {
  url: string;
  reconnectInterval: number;
  maxReconnectAttempts: number;
  heartbeatInterval: number;
}

const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';

const defaultConfig: WsConfig = {
  url: `${wsProto}//${window.location.host}/ws/eeg/`,
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
  private isManualDisconnect = false; // 标记是否是主动断开
  private connectionCount = 0;
  private _subRefCounts: Map<string, number> = new Map();
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

  connect(trackReference = true) {
    if (trackReference) {
      this.connectionCount++;
    } else {
    }
    
    // 如果已经连接或正在连接，直接返回
    if (this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    if (this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    if (!trackReference && this.connectionCount <= 0) {
      console.warn('[WebSocket] Reconnect skipped because there are no active consumers');
      return;
    }

    this.setStatus('connecting');
    this.isManualDisconnect = false;

    try {
      this.ws = new WebSocket(this.config.url);

      this.ws.onopen = () => {
        this.setStatus('connected');
        this.reconnectAttempts = 0;
        this.startHeartbeat();

        // 重连后恢复所有引用计数 >0 的节点订阅
        this._resubscribeAll();
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
        this.setStatus('disconnected');
        this.stopHeartbeat();
        this.ws = null;

        if (!this.isManualDisconnect) {
          this.attemptReconnect();
        } else {
          this.isManualDisconnect = false;
        }
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
      this.setStatus('error');
      this.attemptReconnect();
    }
  }

  disconnect() {
    // 减少连接计数器
    if (this.connectionCount > 0) {
      this.connectionCount--;
    }
    
    // 只有当所有组件都断开连接时才真正断开WebSocket
    if (this.connectionCount <= 0) {
      this.isManualDisconnect = true; // 标记为主动断开
      this.stopReconnect();
      this.stopHeartbeat();

      if (this.ws) {
        // 发送取消订阅消息
        this.unsubscribeFromNodes();

        this.ws.close();
        this.ws = null;
      }

      this.setStatus('disconnected');
      this.connectionCount = 0; // 重置计数器
    } else {
    }
  }

  // ========== 重连机制 ==========

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      return;
    }

    this.reconnectAttempts++;

    this.reconnectTimer = window.setTimeout(() => {
      this.connect(false);
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
          utcFirstFrameMs: message.utcFirstFrameMs,
          nodeId: message.nodeId,
          nodeType: message.nodeType,
          channels: message.channels,
          channelNames: Array.isArray(message.channelNames) ? message.channelNames : undefined,
          samples: message.samples,
          sampleRate: message.sampleRate,
          fftSize: message.fftSize,
          freqResolution: message.freqResolution,
          spectra: message.spectra,
          spectrum: message.spectrum,
          spectrogramRow: message.spectrogramRow,
          spectrogramDbMin: message.spectrogramDbMin,
          spectrogramDbMax: message.spectrogramDbMax,
          processingDelayMs: message.processingDelayMs,
          runtimeMode: message.runtimeMode,
          nonRealtime: message.nonRealtime,
          performanceWarning: message.performanceWarning,
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

  // ========== 订阅管理（以节点为单位的引用计数）==========

  private _refAdd(nodeId: string): boolean {
    const prev = this._subRefCounts.get(nodeId) || 0;
    this._subRefCounts.set(nodeId, prev + 1);
    return prev === 0;
  }

  private _refRemove(nodeId: string): boolean {
    const prev = this._subRefCounts.get(nodeId) || 0;
    if (prev <= 1) {
      this._subRefCounts.delete(nodeId);
      return true;
    }
    this._subRefCounts.set(nodeId, prev - 1);
    return false;
  }

  private _sendWire(action: 'subscribe' | 'unsubscribe', nodeIds: string[]) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: action, nodeIds }));
  }

  private _resubscribeAll() {
    const ids = Array.from(this._subRefCounts.keys());
    if (ids.length > 0) {
      this._sendWire('subscribe', ids);
    }
  }

  subscribe(nodeIds: string[]) {
    const newSubs: string[] = [];
    for (const nid of nodeIds) {
      if (this._refAdd(nid)) newSubs.push(nid);
    }
    if (newSubs.length > 0) {
      this._sendWire('subscribe', newSubs);
    }
  }

  unsubscribe(nodeIds: string[]) {
    const removals: string[] = [];
    for (const nid of nodeIds) {
      if (this._refRemove(nid)) removals.push(nid);
    }
    if (removals.length > 0) {
      this._sendWire('unsubscribe', removals);
    }
  }

  // 保留向后兼容：断开时清空所有订阅
  private unsubscribeFromNodes() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this._subRefCounts.clear();
    this.ws.send(JSON.stringify({ type: 'unsubscribe' }));
  }

  updateSubscription() {
    if (this.status === 'connected') {
      this._resubscribeAll();
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
