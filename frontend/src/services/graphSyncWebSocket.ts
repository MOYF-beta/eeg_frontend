import type { GraphPayload } from './graph';

type SyncStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

export interface GraphSyncMessage {
  graph: GraphPayload;
  reason?: string;
  timestamp?: number;
}

class GraphSyncWebSocket {
  private ws: WebSocket | null = null;
  private status: SyncStatus = 'disconnected';
  private listeners = {
    onGraph: new Set<(message: GraphSyncMessage) => void>(),
    onStatus: new Set<(status: SyncStatus) => void>(),
  };

  private reconnectAttempts = 0;
  private reconnectTimer: number | null = null;
  private heartbeatTimer: number | null = null;
  private isManualDisconnect = false;

  private readonly maxReconnectAttempts = 5;
  private readonly reconnectInterval = 3000;
  private readonly heartbeatInterval = 30000;

  private get url() {
    return `ws://${window.location.hostname}:8000/ws/graph-sync/`;
  }

  connect() {
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
      this.send({ type: 'get_graph' });
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data || '{}');
        if (message.type === 'pong') return;
        if (message.type === 'graph_state' && message.graph) {
          this.listeners.onGraph.forEach((cb) => cb({
            graph: message.graph as GraphPayload,
            reason: message.reason,
            timestamp: message.timestamp,
          }));
        }
      } catch (err) {
        console.error('[GraphSyncWS] Failed to parse message:', err);
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

  disconnect() {
    this.isManualDisconnect = true;
    this.stopReconnect();
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[GraphSyncWS] Max reconnection attempts reached');
      return;
    }
    this.reconnectAttempts++;
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, this.reconnectInterval);
  }

  private stopReconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.reconnectAttempts = 0;
  }

  private startHeartbeat() {
    this.heartbeatTimer = window.setInterval(() => {
      this.send({ type: 'ping' });
    }, this.heartbeatInterval);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  onGraph(callback: (message: GraphSyncMessage) => void): () => void {
    this.listeners.onGraph.add(callback);
    return () => this.listeners.onGraph.delete(callback);
  }

  onStatus(callback: (status: SyncStatus) => void): () => void {
    this.listeners.onStatus.add(callback);
    return () => this.listeners.onStatus.delete(callback);
  }

  private send(payload: Record<string, unknown>) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify(payload));
  }

  private setStatus(status: SyncStatus) {
    this.status = status;
    this.listeners.onStatus.forEach((cb) => cb(status));
  }
}

export const graphSyncWebSocket = new GraphSyncWebSocket();
