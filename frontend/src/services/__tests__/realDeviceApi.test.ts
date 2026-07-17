import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { realDeviceApi } from '../realDeviceApi';
import type { DeviceConnectionStatus } from '../realDeviceApi';

const MOCK_PORTS = {
  ok: true, data: {
    ports: [
      { port: 'sim_alpha', description: 'Alpha', driver_type: 'simulated', channel_count: 8, sample_rate: 250, is_available: true },
      { port: 'sim_beta', description: 'Beta', driver_type: 'simulated', channel_count: 8, sample_rate: 250, is_available: true },
    ],
  },
};

const MOCK_CONNECTED: DeviceConnectionStatus = {
  device_id: 'sim_alpha', driver_type: 'simulated', name: 'Alpha',
  status: 'connected', channel_count: 8, sample_rate: 250,
};

function mockOk(data: any) {
  (globalThis.fetch as any).mockResolvedValue({ ok: true, json: () => Promise.resolve({ ok: true, data }) });
}
function mockFail() {
  (globalThis.fetch as any).mockResolvedValue({ ok: false, json: () => Promise.resolve({ ok: false, error: 'err' }) });
}

describe('realDeviceApi', () => {
  beforeEach(() => { vi.stubGlobal('fetch', vi.fn()); });
  afterEach(() => { vi.unstubAllGlobals(); });

  describe('scanPorts', () => {
    it('应返回设备端口列表', async () => {
      mockOk(MOCK_PORTS.data);
      const ports = await realDeviceApi.scanPorts();
      expect(ports).toHaveLength(2);
      expect(ports[0].port).toBe('sim_alpha');
    });
    it('网络错误应返回空列表', async () => {
      (globalThis.fetch as any).mockRejectedValue(new Error('err'));
      expect(await realDeviceApi.scanPorts()).toEqual([]);
    });
  });

  describe('connectDevice', () => {
    it('成功应返回设备状态', async () => {
      mockOk(MOCK_CONNECTED);
      const s = await realDeviceApi.connectDevice('sim_alpha');
      expect(s).not.toBeNull();
      expect(s!.status).toBe('connected');
    });
    it('失败应返回 null', async () => {
      mockFail();
      expect(await realDeviceApi.connectDevice('x')).toBeNull();
    });
  });

  describe('getSingleDeviceStatus', () => {
    it('应返回状态信息', async () => {
      mockOk({ status: 'acquiring', pending_count: 42 });
      const s = await realDeviceApi.getSingleDeviceStatus('sim_alpha');
      expect(s).not.toBeNull();
      expect(s!.status).toBe('acquiring');
      expect(s!.pending_count).toBe(42);
    });
  });

  describe('startAcquisition', () => {
    it('成功应返回 true', async () => {
      mockOk(null);
      expect(await realDeviceApi.startAcquisition('sim_alpha')).toBe(true);
    });
    it('失败应返回 false', async () => {
      mockFail();
      expect(await realDeviceApi.startAcquisition('sim_alpha')).toBe(false);
    });
  });

  describe('stopAcquisition', () => {
    it('成功应返回 true', async () => { mockOk(null); expect(await realDeviceApi.stopAcquisition('sim_alpha')).toBe(true); });
  });

  describe('disconnectDevice', () => {
    it('成功应返回 true', async () => { mockOk(null); expect(await realDeviceApi.disconnectDevice('sim_alpha')).toBe(true); });
  });

  describe('getDebugOutput', () => {
    it('应返回调试数据', async () => {
      mockOk({ device_id: 'sim_alpha', frames: [{ seq: 1, channels: [1.0] }] });
      expect(await realDeviceApi.getDebugOutput('sim_alpha')).not.toBeNull();
    });
  });

  describe('端点正确性', () => {
    it('startAcquisition 使用 POST + 正确路径', async () => {
      mockOk(null);
      await realDeviceApi.startAcquisition('sim_alpha');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('sim_alpha/start-acquisition'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
    it('disconnectDevice 使用 POST + 正确路径', async () => {
      mockOk(null);
      await realDeviceApi.disconnectDevice('sim_alpha');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('sim_alpha/disconnect'),
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });
});
