import type { Device, SimulatedDeviceConfig } from './sessionStore';

// 后端设备原始格式（/api/devices/ 返回的 data 字段结构）
export interface RawDevice {
  id: string;
  name: string;
  type: string;
  sampling_rate: number;
  channel_count: number;
  config: Record<string, unknown>;
  created_at?: number;
  updated_at?: number;
  connection_status?: Record<string, unknown>;
}

// 统一响应格式
interface ApiResponse<T> {
  ok: boolean;
  data?: T;
  error?: string;
}

// 创建设备请求接口
interface CreateDeviceRequest {
  type: 'simulated' | 'physical';
  name: string;
  alias?: string;
  address: string;
  sampling_rate: number;
  channel_count: number;
  config?: {
    channels: Array<{
      index: number;
      wave_type: string;
      frequency: number;
      amplitude: number;
      alias?: string;
      phase?: number;
      duty_cycle?: number;
      pulse_width?: number;
      sine_components?: Array<{
        frequency: number;
        amplitude: number;
        phase: number;
      }>;
      noise_type?: string;
      noise_amplitude?: number;
      noise_seed?: number;
      noise_cutoff_frequency?: number;
      enabled?: boolean;
    }>;
    global_noise?: {
      type: string;
      amplitude: number;
      seed?: number;
      cutoff_frequency?: number;
    };
  };
}

// 更新设备请求接口
interface UpdateDeviceRequest {
  name?: string;
  alias?: string;
  address?: string;
  sampling_rate?: number;
  channel_count?: number;
  config?: CreateDeviceRequest['config'];
}

// 设备API服务
export const deviceApi = {
  // 获取设备列表（原始后端格式）—— 统一从 /api/real-devices/ 获取
  async fetchDevicesRaw(): Promise<RawDevice[]> {
    const response = await fetch('/api/real-devices/');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const result: ApiResponse<{ devices: RawDevice[]; count: number }> = await response.json();
    if (!result.ok) {
      throw new Error(result.error || 'Failed to fetch devices');
    }
    return result.data?.devices ?? [];
  },

  // 获取设备列表
  async getDevices(): Promise<Device[]> {
    try {
      const rawDevices = await this.fetchDevicesRaw();
      return rawDevices.map((device) => ({
        id: device.id,
        name: device.name,
        status: (device as any).status === 'online' || (device.config?.connected as boolean) ? 'online' : 'offline',
        type: (device.type === 'wearable_eeg' || device.type === 'ch340_eeg') ? 'real' : 'simulated',
        samplingRate: device.sampling_rate,
        channelCount: device.channel_count,
        config: device.config || {},
      }));
    } catch (error) {
      console.error('Failed to fetch devices:', error);
      throw error;
    }
  },

  // 创建设备
  async createDevice(deviceData: CreateDeviceRequest): Promise<Device> {
    try {
      const response = await fetch('/api/devices/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(deviceData),
      });
      
      const result: ApiResponse<Device> = await response.json();
      
      if (!response.ok || !result.ok) {
        throw new Error(result.error || `HTTP error! status: ${response.status}`);
      }
      
      if (!result.data) {
        throw new Error('Empty response from server');
      }
      return result.data;
    } catch (error) {
      console.error('Failed to create device:', error);
      throw error;
    }
  },

  // 更新设备
  async updateDevice(deviceId: string, updates: UpdateDeviceRequest): Promise<Device> {
    try {
      const response = await fetch(`/api/devices/${deviceId}/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });
      
      const result: ApiResponse<Device> = await response.json();
      
      if (!response.ok || !result.ok) {
        let errorMessage = result.error || `HTTP error! status: ${response.status}`;
        if (response.status === 403) {
          errorMessage = '计算图正在运行中，无法修改设备';
        }
        throw new Error(errorMessage);
      }
      
      if (!result.data) {
        throw new Error('Empty response from server');
      }
      return result.data;
    } catch (error) {
      console.error('Failed to update device:', error);
      throw error;
    }
  },

  // 删除设备
  async deleteDevice(deviceId: string): Promise<void> {
    try {
      const response = await fetch(`/api/devices/${deviceId}/`, {
        method: 'DELETE',
      });
      
      const result: ApiResponse<void> = await response.json();
      
      if (!response.ok || !result.ok) {
        let errorMessage = result.error || `HTTP error! status: ${response.status}`;
        if (response.status === 403) {
          errorMessage = '计算图正在运行中，无法删除设备';
        }
        throw new Error(errorMessage);
      }
    } catch (error) {
      console.error('Failed to delete device:', error);
      throw error;
    }
  },

  // 转换前端配置为API格式
  convertToApiConfig(config: SimulatedDeviceConfig): CreateDeviceRequest['config'] {
    if (!config) return undefined;

    return {
      channels: config.channels.map(channel => ({
        index: channel.index,
        wave_type: this.mapSignalType(channel.signal.type),
        frequency: channel.signal.frequency,
        amplitude: channel.signal.amplitude,
        phase: channel.signal.phase || 0,
        duty_cycle: channel.signal.dutyCycle,
        pulse_width: channel.signal.pulseWidth,
        sine_components: channel.signal.sineComponents?.map(comp => ({
          frequency: comp.frequency,
          amplitude: comp.amplitude,
          phase: comp.phase
        })),
        noise_type: channel.noise?.type || 'none',
        noise_amplitude: channel.noise?.amplitude || 0,
        noise_seed: channel.noise?.seed,
        noise_cutoff_frequency: channel.noise?.cutoffFrequency,
        enabled: channel.enabled
      })),
      global_noise: config.globalNoise ? {
        type: config.globalNoise.type,
        amplitude: config.globalNoise.amplitude,
        seed: config.globalNoise.seed,
        cutoff_frequency: config.globalNoise.cutoffFrequency
      } : undefined
    };
  },

  // 映射信号类型
  mapSignalType(type: string): string {
    const mapping: Record<string, string> = {
      'sine': 'sine',
      'square': 'square',
      'triangle': 'triangle',
      'pulse': 'pulse',
      'multi_sine': 'multi_sine'
    };
    return mapping[type] || 'sine';
  },

  // 从API格式转换回前端配置
  convertFromApiConfig(apiConfig: any): SimulatedDeviceConfig | undefined {
    if (!apiConfig || !apiConfig.channels) return undefined;

    return {
      channels: apiConfig.channels.map((channel: any) => ({
        index: channel.index,
        enabled: channel.enabled !== false,
        signal: {
          type: this.reverseMapSignalType(channel.wave_type),
          frequency: channel.frequency || 10,
          amplitude: channel.amplitude || 100,
          phase: channel.phase || 0,
          dutyCycle: channel.duty_cycle,
          pulseWidth: channel.pulse_width,
          sineComponents: channel.sine_components?.map((comp: any) => ({
            frequency: comp.frequency,
            amplitude: comp.amplitude,
            phase: comp.phase
          }))
        },
        noise: channel.noise_type && channel.noise_type !== 'none' ? {
          type: channel.noise_type,
          amplitude: channel.noise_amplitude || 0,
          seed: channel.noise_seed,
          cutoffFrequency: channel.noise_cutoff_frequency
        } : undefined
      })),
      globalNoise: apiConfig.global_noise ? {
        type: apiConfig.global_noise.type,
        amplitude: apiConfig.global_noise.amplitude,
        seed: apiConfig.global_noise.seed,
        cutoffFrequency: apiConfig.global_noise.cutoff_frequency
      } : undefined
    };
  },

  // 反向映射信号类型
  reverseMapSignalType(type: string): string {
    const mapping: Record<string, string> = {
      'sine': 'sine',
      'square': 'square',
      'triangle': 'triangle',
      'pulse': 'pulse',
      'multi_sine': 'multi_sine'
    };
    
    // 查找匹配的键
    for (const [key, value] of Object.entries(mapping)) {
      if (value === type) return key;
    }
    return 'sine';
  }
};