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
    it('应返回调试数据（含 raw_inputs）', async () => {
      mockOk({
        ports: [{
          port: 'sim_alpha',
          samples: [{ seq: 1, timestamp: 1.0, channels: [1.0], port: 'sim_alpha', raw_hex: '' }],
          count: 1,
          raw_inputs: [{ timestamp: 1.0, raw_hex: 'aabb', raw_text: '' }],
          raw_input_count: 1,
        }],
        total_samples: 1,
      });
      const out = await realDeviceApi.getDebugOutput('sim_alpha');
      expect(out.ports).toHaveLength(1);
      expect(out.ports[0].raw_input_count).toBe(1);
      expect(out.ports[0].raw_inputs![0].raw_hex).toBe('aabb');
    });
  });

  describe('getDrivers', () => {
    it('应返回已加载驱动列表并更新 reactive state', async () => {
      const drivers = [
        { driver_type: 'wearable_eeg', driver_name: 'CH340', driver_description: '', device_count: 0, module: 'm', class_name: 'Ch340EegDriver' },
        { driver_type: 'simulated', driver_name: '模拟', driver_description: 'd', device_count: 5, module: 'm2', class_name: 'SimulatorDriver' },
      ];
      mockOk({ drivers, count: 2 });
      const result = await realDeviceApi.getDrivers();
      expect(result).toHaveLength(2);
      expect(result[0].driver_type).toBe('wearable_eeg');
      expect(realDeviceApi.drivers.value).toHaveLength(2);
    });
    it('网络错误应返回空列表', async () => {
      (globalThis.fetch as any).mockRejectedValue(new Error('err'));
      expect(await realDeviceApi.getDrivers()).toEqual([]);
    });
    it('应请求正确端点', async () => {
      mockOk({ drivers: [], count: 0 });
      await realDeviceApi.getDrivers();
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/real-devices/drivers/'),
      );
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

  describe('驱动故障反馈（last_error / error）', () => {
    beforeEach(() => { realDeviceApi.error.value = null; });

    it('connectDevice 失败时 error.value 包含后端返回的具体原因', async () => {
      (globalThis.fetch as any).mockResolvedValue({
        ok: false,
        json: () => Promise.resolve({
          ok: false,
          error: '模拟连接失败：握手超时',
          data: { last_error: '模拟连接失败：握手超时' },
        }),
      });
      const result = await realDeviceApi.connectDevice('flt_conn_err');
      expect(result).toBeNull();
      expect(realDeviceApi.error.value).toContain('握手超时');
    });

    it('connectDevice 失败后 getDevices 不清除错误消息', async () => {
      // 第一次调用：connect 返回 500
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ ok: false, error: '驱动连接失败原因X' }),
      });
      // 第二次调用（connectDevice 内部调 getDevices）：返回设备列表成功
      (globalThis.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ok: true, data: { devices: [], count: 0 } }),
      });
      await realDeviceApi.connectDevice('flt_x');
      // 即使 getDevices 成功，刚才的连接失败原因仍保留（不被覆盖）
      expect(realDeviceApi.error.value).toBe('驱动连接失败原因X');
    });

    it('getDevices 成功时清除旧的 error', async () => {
      realDeviceApi.error.value = '旧错误';
      mockOk({ devices: [], count: 0 });
      await realDeviceApi.getDevices();
      expect(realDeviceApi.error.value).toBeNull();
    });

    it('getDevices 失败时保留已有的更具体错误', async () => {
      realDeviceApi.error.value = '具体驱动错误';
      (globalThis.fetch as any).mockRejectedValue(new Error('network'));
      await realDeviceApi.getDevices();
      expect(realDeviceApi.error.value).toBe('具体驱动错误');
    });
  });
});
