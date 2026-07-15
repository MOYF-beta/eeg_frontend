/**
 * 设备管理API服务 - 统一设备管理
 */

import { ref } from 'vue'
import { deviceApi, type RawDevice } from './deviceApi'

// 串口设备接口
export interface SerialPort {
  port: string
  description: string
  manufacturer: string
  product: string
  hwid: string
  is_ch340: boolean
  is_available: boolean
}

// 设备连接状态
export interface DeviceConnectionStatus {
  port: string
  status: 'disconnected' | 'connecting' | 'connected' | 'acquiring' | 'error'
  baudrate: number
  last_error: string | null
  connected_at: number | null
  data_count: number
  queue_size: number
}

// 统一设备信息接口
export interface DeviceInfo {
  id: string
  name: string
  type: 'simulated' | 'wearable_eeg'
  sampling_rate: number
  channel_count: number
  config: {
    port?: string
    baudrate?: number
    connected?: boolean
    acquiring?: boolean
    description?: string
    manufacturer?: string
    product?: string
    hwid?: string
    is_ch340?: boolean
    vid?: string | number
    pid?: string | number
    channels?: Array<{
      index: number
      wave_type: string
      frequency: number
      amplitude: number
      alias: string
      noise_type?: string
      noise_amplitude?: number
      duty_cycle?: number
    }>
  }
  created_at: number
  updated_at: number
  connection_status?: DeviceConnectionStatus
}

export interface SerialDebugSample {
  timestamp: number
  channels: number[]
  port: string
  raw_hex?: string
}

export interface SerialRawInput {
  timestamp: number
  raw_hex: string
  raw_text?: string
}

export interface SerialDebugPortOutput {
  port: string
  samples: SerialDebugSample[]
  count: number
  raw_inputs?: SerialRawInput[]
  raw_input_count?: number
}

export interface SerialDebugOutput {
  ports: SerialDebugPortOutput[]
  total_samples: number
}

// 统一响应格式
interface ApiResponse<T = any> {
  ok: boolean
  data?: T
  error?: string
}

class RealDeviceApi {
  private baseUrl = '/api/real-devices'
  
  // 状态管理 - 统一设备列表
  public ports = ref<SerialPort[]>([])
  public devices = ref<DeviceInfo[]>([])
  public isLoading = ref(false)
  public error = ref<string | null>(null)

  /**
   * 扫描可用的串口设备
   */
  async scanPorts(): Promise<SerialPort[]> {
    this.isLoading.value = true
    this.error.value = null
    
    try {
      const response = await fetch(`${this.baseUrl}/scan-ports/`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse<{ ports: SerialPort[] }> = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      this.ports.value = result.data.ports
      return result.data.ports
      
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to scan ports:', err)
      return []
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 连接真实设备
   */
  async connectDevice(port: string, baudrate: number = 460800, deviceId?: string): Promise<DeviceConnectionStatus | null> {
    this.isLoading.value = true
    this.error.value = null
    
    try {
      const response = await fetch(`${this.baseUrl}/connect/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          port,
          baudrate,
          device_id: deviceId
        })
      })

      const result: ApiResponse<DeviceConnectionStatus> = await response.json()

      if (!response.ok) {
        throw new Error(result?.error || `HTTP error! status: ${response.status}`)
      }
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      // 更新设备列表
      await this.getDevices()
      
      return result.data
      
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to connect device:', err)
      return null
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 开始设备数据采集
   */
  async startAcquisition(port: string): Promise<boolean> {
    this.isLoading.value = true
    this.error.value = null
    
    try {
      const encodedPort = encodeURIComponent(port)
      const response = await fetch(`${this.baseUrl}/${encodedPort}/start-acquisition/`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      // 更新设备列表
      await this.getDevices()
      
      return true
      
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to start acquisition:', err)
      return false
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 停止设备数据采集
   */
  async stopAcquisition(port: string): Promise<boolean> {
    this.isLoading.value = true
    this.error.value = null
    
    try {
      const encodedPort = encodeURIComponent(port)
      const response = await fetch(`${this.baseUrl}/${encodedPort}/stop-acquisition/`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      // 更新设备列表
      await this.getDevices()
      
      return true
      
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to stop acquisition:', err)
      return false
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 断开设备连接
   */
  async disconnectDevice(port: string): Promise<boolean> {
    this.isLoading.value = true
    this.error.value = null
    
    try {
      const encodedPort = encodeURIComponent(port)
      const response = await fetch(`${this.baseUrl}/${encodedPort}/disconnect/`, {
        method: 'POST'
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      // 更新设备列表
      await this.getDevices()
      
      return true
      
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to disconnect device:', err)
      return false
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 获取单个设备状态
   */
  async getSingleDeviceStatus(port: string): Promise<DeviceConnectionStatus | null> {
    try {
      const encodedPort = encodeURIComponent(port)
      const response = await fetch(`${this.baseUrl}/${encodedPort}/status/`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse<DeviceConnectionStatus> = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      return result.data
      
    } catch (err) {
      console.error('Failed to get device status:', err)
      return null
    }
  }

  /**
   * 获取所有设备（统一设备列表）
   */
  async getDevices(): Promise<DeviceInfo[]> {
    this.isLoading.value = true
    this.error.value = null

    try {
      const rawDevices = await deviceApi.fetchDevicesRaw()
      this.devices.value = rawDevices as unknown as DeviceInfo[]
      return this.devices.value

    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to get devices:', err)
      return []
    } finally {
      this.isLoading.value = false
    }
  }

  /**
   * 获取设备连接状态
   */
  async getDeviceStatus(): Promise<DeviceConnectionStatus[]> {
    try {
      const response = await fetch(`${this.baseUrl}/status/`)
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result: ApiResponse<{ devices: DeviceConnectionStatus[] }> = await response.json()
      
      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }
      
      return result.data.devices
      
    } catch (err) {
      console.error('Failed to get device status:', err)
      return []
    }
  }

  /**
   * 获取串口调试输出
   */
  async getDebugOutput(port?: string, count: number = 200): Promise<SerialDebugOutput> {
    try {
      const params = new URLSearchParams()
      if (port) params.set('port', port)
      params.set('count', String(count))

      const response = await fetch(`${this.baseUrl}/debug-output/?${params.toString()}`)

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const result: ApiResponse<SerialDebugOutput> = await response.json()

      if (!result.ok) {
        throw new Error(result.error || "Request failed")
      }

      return result.data
    } catch (err) {
      this.error.value = err instanceof Error ? err.message : 'Unknown error'
      console.error('Failed to get debug output:', err)
      return { ports: [], total_samples: 0 }
    }
  }

  /**
   * 获取设备状态文本
   */
  getStatusText(status: string): string {
    const statusMap: Record<string, string> = {
      'disconnected': '未连接',
      'connecting': '连接中',
      'connected': '已连接',
      'acquiring': '采集中',
      'error': '错误'
    }
    return statusMap[status] || status
  }

  /**
   * 获取设备状态颜色
   */
  getStatusColor(status: string): string {
    const colorMap: Record<string, string> = {
      'disconnected': 'grey',
      'connecting': 'orange',
      'connected': 'blue',
      'acquiring': 'green',
      'error': 'red'
    }
    return colorMap[status] || 'grey'
  }

  /**
   * 获取设备状态图标
   */
  getStatusIcon(status: string): string {
    const iconMap: Record<string, string> = {
      'disconnected': 'mdi-link-off',
      'connecting': 'mdi-link',
      'connected': 'mdi-link',
      'acquiring': 'mdi-play',
      'error': 'mdi-alert'
    }
    return iconMap[status] || 'mdi-help'
  }

  /**
   * 检查设备是否支持
   */
  isDeviceSupported(port: SerialPort): boolean {
    // 支持CH340/CH341芯片的设备
    return port.is_ch340 || port.is_available
  }

  /**
   * 获取推荐的波特率选项
   */
  getBaudrateOptions(): number[] {
    return [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
  }

  /**
   * 自动检测最佳波特率
   */
  detectBestBaudrate(port: SerialPort): number {
    // CH340设备通常使用460800波特率
    if (port.is_ch340) {
      return 460800
    }
    
    // 其他设备默认使用115200
    return 115200
  }
}

// 创建全局实例
export const realDeviceApi = new RealDeviceApi()

// 导出类型
export type { RealDeviceApi }