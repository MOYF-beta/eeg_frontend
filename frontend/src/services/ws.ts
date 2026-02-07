export type EegPacket = {
  t: number;
  channels: number[];
};

export function createEegSocket(
  url: string,
  onPacket: (packet: EegPacket) => void,
  onStatus?: (status: 'open' | 'close' | 'error') => void,
) {
  const ws = new WebSocket(url);
  ws.onopen = () => onStatus?.('open');
  ws.onclose = () => onStatus?.('close');
  ws.onerror = () => onStatus?.('error');
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as EegPacket;
      if (Array.isArray(data.channels)) {
        onPacket(data);
      }
    } catch {
      // ignore malformed messages
    }
  };
  return ws;
}
