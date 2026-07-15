/**
 * 统一控制 WebSocket (ws/control/)
 *
 * 替代前端所有控制相关的 HTTP 轮询：
 * - 前端→后端: run, stop, freeze, sync_graph, save_graph, connect_device,
 *              start_streaming, stop_streaming, scan_ports, record
 * - 后端→前端: state（含 graph + runtime + devices 全量推送）
 *
 * 前端组件通过 subscribeState() 监听状态变化，不再 setInterval 轮询。
 */

import type { GraphPayload } from './graph';

export type ControlStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface DeviceStatusInfo {
  device_id: string;
  driver_type: string;
  name: string;
  status: string;
  channel_count: number;
  sample_rate: number;
}

export interface ControlState {
  graph: GraphPayload;
  runtime: {
    running: boolean;
    mode: string;
    startedAt: number | null;
    stoppedAt: number | null;
    progress: number | null;
    processingDelayMs: number;
    nonRealtime: boolean;
    warning: string | null;
    frozen: boolean;
  };
  devices: DeviceStatusInfo[];
  reason?: string;
}

export interface CmdResult {
  type: 'cmd_result';
  command: string;
  ok: boolean;
  error?: string;
  [key: string]: unknown;
}

type StateListener = (state: ControlState) => void;
type CmdResultListener = (result: CmdResult) => void;
type StatusListener = (status: ControlStatus) => void;

class ControlWebSocket {
  private ws: WebSocket | null = null;
  private _status: ControlStatus = 'disconnected';

  private stateListeners = new Set<StateListener>();
  private cmdResultListeners = new Set<CmdResultListener>();
  private statusListeners = new Set<StatusListener>();

  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private isManualDisconnect = false;

  private readonly maxReconnectAttempts = 10;
  private readonly reconnectInterval = 3000;
  private readonly heartbeatInterval = 30000;

  private lastState: ControlState | null = null;

  get status(): ControlStatus {
    return this._status;
  }

  get current(): ControlState | null {
    return this.lastState;
  }

  private get url(): string {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}/ws/control/`;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return;
    }

    this.isManualDisconnect = false;
    this.setStatus('connecting');
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      this.setStatus('connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data || '{}');
        if (msg.type === 'pong') return;

        if (msg.type === 'state') {
          this.lastState = {
            graph: msg.graph,
            runtime: msg.runtime,
            devices: msg.devices || [],
            reason: msg.reason,
          };
          this.stateListeners.forEach((cb) => cb(this.lastState!));
        } else if (msg.type === 'cmd_result') {
          this.cmdResultListeners.forEach((cb) => cb(msg as CmdResult));
        } else if (msg.type === 'error') {
          console.warn('[ControlWS] Server error:', msg.error);
        }
      } catch (err) {
        console.error('[ControlWS] Parse error:', err);
      }
    };

    this.ws.onerror = () => {
      this.setStatus('error');
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.stopHeartbeat();
      this.setStatus('disconnected');
      if (!this.isManualDisconnect) {
        this.attemptReconnect();
      }
    };
  }

  disconnect(): void {
    this.isManualDisconnect = true;
    this.stopReconnect();
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  isConnected(): boolean {
    return this._status === 'connected';
  }

  // ------------------------------------------------------------------ #
  //  命令发送
  // ------------------------------------------------------------------ #
  send(type: string, payload: Record<string, unknown> = {}): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type, ...payload }));
  }

  run(mode: 'live' | 'offline' = 'live'): void {
    this.send('run', { mode });
  }

  stop(): void {
    this.send('stop');
  }

  freeze(frozen: boolean): void {
    this.send('freeze', { frozen });
  }

  syncGraph(graph: GraphPayload, baseRevision?: number): void {
    this.send('sync_graph', { graph, baseRevision });
  }

  saveGraph(): void {
    this.send('save_graph');
  }

  connectDevice(deviceId: string, config?: Record<string, unknown>): void {
    this.send('connect_device', { device_id: deviceId, config });
  }

  disconnectDevice(deviceId: string): void {
    this.send('disconnect_device', { device_id: deviceId });
  }

  startStreaming(deviceId: string): void {
    this.send('start_streaming', { device_id: deviceId });
  }

  stopStreaming(deviceId: string): void {
    this.send('stop_streaming', { device_id: deviceId });
  }

  scanPorts(): void {
    this.send('scan_ports');
  }

  record(action: 'start' | 'stop'): void {
    this.send('record', { action });
  }

  // ------------------------------------------------------------------ #
  //  订阅
  // ------------------------------------------------------------------ #
  onState(cb: StateListener): () => void {
    this.stateListeners.add(cb);
    // 如果已有缓存状态，立即回调
    if (this.lastState) {
      cb(this.lastState);
    }
    return () => this.stateListeners.delete(cb);
  }

  onCmdResult(cb: CmdResultListener): () => void {
    this.cmdResultListeners.add(cb);
    return () => this.cmdResultListeners.delete(cb);
  }

  onStatus(cb: StatusListener): () => void {
    this.statusListeners.add(cb);
    return () => this.statusListeners.delete(cb);
  }

  // ------------------------------------------------------------------ #
  //  内部
  // ------------------------------------------------------------------ #
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[ControlWS] Max reconnection attempts reached');
      return;
    }
    this.reconnectAttempts++;
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  private stopReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = window.setInterval(() => {
      this.send('ping');
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private setStatus(status: ControlStatus): void {
    this._status = status;
    this.statusListeners.forEach((cb) => cb(status));
  }
}

export const controlWebSocket = new ControlWebSocket();
