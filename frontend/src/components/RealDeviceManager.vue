<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-usb</v-icon>
        真实设备管理
      </div>
      <div class="d-flex align-center ga-2">
        <v-btn 
          color="primary" 
          size="small" 
          @click="scanPorts"
          :loading="realDeviceApi.isLoading.value"
        >
          <v-icon left>mdi-magnify</v-icon>
          扫描串口
        </v-btn>
        <v-btn 
          color="secondary" 
          size="small" 
          @click="showAddDeviceDialog = true"
        >
          <v-icon left>mdi-plus</v-icon>
          添加设备
        </v-btn>
      </div>
    </v-card-title>
    
    <v-divider />
    
    <!-- 错误提示 -->
    <v-alert 
      v-if="realDeviceApi.error.value" 
      type="error" 
      density="compact" 
      variant="tonal" 
      class="ma-2"
      closable
      @click:close="realDeviceApi.error.value = null"
    >
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-alert</v-icon>
        <span>{{ realDeviceApi.error.value }}</span>
      </div>
    </v-alert>
    
    <v-card-text>
      <!-- 串口设备列表 -->
      <v-expansion-panels v-model="expandedPanels" multiple class="mb-4">
        <v-expansion-panel>
          <v-expansion-panel-title>
            <div class="d-flex align-center">
              <v-icon class="mr-2">mdi-serial-port</v-icon>
              可用串口设备 ({{ realDeviceApi.ports.value.length }})
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item
                v-for="port in realDeviceApi.ports.value"
                :key="port.port"
                :class="{ 'bg-green-lighten-5': port.is_ch340 }"
              >
                <template v-slot:prepend>
                  <v-icon :color="port.is_ch340 ? 'green' : 'grey'">
                    {{ port.is_ch340 ? 'mdi-chip' : 'mdi-usb-port' }}
                  </v-icon>
                </template>
                
                <v-list-item-title>
                  <strong>{{ port.port }}</strong>
                  <v-chip size="x-small" class="ml-2" :color="port.is_available ? 'success' : 'warning'">
                    {{ port.is_available ? '可用' : '不可用' }}
                  </v-chip>
                  <v-chip v-if="port.is_ch340" size="x-small" color="green" class="ml-1">
                    CH340
                  </v-chip>
                </v-list-item-title>
                
                <v-list-item-subtitle>
                  {{ port.description || '未知设备' }}
                  <span v-if="port.manufacturer"> - {{ port.manufacturer }}</span>
                  <span v-if="port.product"> - {{ port.product }}</span>
                </v-list-item-subtitle>
                
                <template v-slot:append>
                  <v-btn
                    size="small"
                    color="primary"
                    :disabled="!port.is_available"
                    @click="connectToPort(port)"
                  >
                    <v-icon left>mdi-link</v-icon>
                    连接
                  </v-btn>
                </template>
              </v-list-item>
              
              <v-list-item v-if="realDeviceApi.ports.value.length === 0">
                <v-list-item-title class="text-grey">
                  未检测到串口设备
                </v-list-item-title>
                <v-list-item-subtitle>
                  请确保设备已连接并安装了正确的驱动程序
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
        
        <v-expansion-panel>
          <v-expansion-panel-title>
            <div class="d-flex align-center">
              <v-icon class="mr-2">mdi-connection</v-icon>
              已连接设备 ({{ connectedDevices.length }})
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item
                v-for="device in connectedDevices"
                :key="device.id"
              >
                <template v-slot:prepend>
                  <v-icon :color="realDeviceApi.getStatusColor(device.status)">
                    {{ realDeviceApi.getStatusIcon(device.status) }}
                  </v-icon>
                </template>
                
                <v-list-item-title>
                  <strong>{{ device.port }}</strong>
                  <v-chip 
                    size="x-small" 
                    class="ml-2" 
                    :color="realDeviceApi.getStatusColor(device.status)"
                  >
                    {{ realDeviceApi.getStatusText(device.status) }}
                  </v-chip>
                </v-list-item-title>
                
                <v-list-item-subtitle>
                  波特率: {{ device.baudrate }}
                  <span v-if="device.connected_at">
                    | 连接时间: {{ formatTime(device.connected_at) }}
                  </span>
                  <span v-if="device.data_count > 0">
                    | 数据包: {{ device.data_count }}
                  </span>
                  <span v-if="device.last_error" class="text-red">
                    | 错误: {{ device.last_error }}
                  </span>
                </v-list-item-subtitle>
                
                <template v-slot:append>
                  <div class="d-flex ga-1">
                    <v-btn
                      v-if="device.status === 'connected'"
                      size="small"
                      color="green"
                      @click="startAcquisition(device.port)"
                    >
                      <v-icon left>mdi-play</v-icon>
                      开始采集
                    </v-btn>
                    
                    <v-btn
                      v-if="device.status === 'acquiring'"
                      size="small"
                      color="orange"
                      @click="stopAcquisition(device.port)"
                    >
                      <v-icon left>mdi-stop</v-icon>
                      停止采集
                    </v-btn>
                    
                    <v-btn
                      size="small"
                      color="red"
                      @click="disconnectDevice(device.port)"
                    >
                      <v-icon left>mdi-link-off</v-icon>
                      断开
                    </v-btn>
                  </div>
                </template>
              </v-list-item>
              
              <v-list-item v-if="connectedDevices.length === 0">
                <v-list-item-title class="text-grey">
                  没有已连接的设备
                </v-list-item-title>
                <v-list-item-subtitle>
                  请先扫描并连接串口设备
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
        
        <v-expansion-panel>
          <v-expansion-panel-title>
            <div class="d-flex align-center">
              <v-icon class="mr-2">mdi-devices</v-icon>
              真实EEG设备 ({{ realDevices.length }})
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-list density="compact">
              <v-list-item
                v-for="device in realDevices"
                :key="device.id"
              >
                <template v-slot:prepend>
                  <v-icon color="blue">mdi-brain</v-icon>
                </template>
                
                <v-list-item-title>
                  <strong>{{ device.name }}</strong>
                  <v-chip size="x-small" class="ml-2" color="blue">
                    可穿戴EEG
                  </v-chip>
                </v-list-item-title>
                
                <v-list-item-subtitle>
                  采样率: {{ device.sampling_rate }} Hz | 通道数: {{ device.channel_count }}
                  <span v-if="device.config.port">
                    | 端口: {{ device.config.port }}
                  </span>
                  <span v-if="device.connection_status">
                    | 状态: {{ realDeviceApi.getStatusText(device.connection_status.status) }}
                  </span>
                </v-list-item-subtitle>
                
                <template v-slot:append>
                  <div class="d-flex ga-1">
                    <v-btn
                      v-if="device.config.port && device.connection_status?.status === 'disconnected'"
                      size="small"
                      color="primary"
                      @click="connectDevice(device)"
                    >
                      <v-icon left>mdi-link</v-icon>
                      连接
                    </v-btn>
                    
                    <v-btn
                      v-if="device.config.port && device.connection_status?.status === 'connected'"
                      size="small"
                      color="green"
                      @click="startDeviceAcquisition(device)"
                    >
                      <v-icon left>mdi-play</v-icon>
                      开始采集
                    </v-btn>
                    
                    <v-btn
                      v-if="device.config.port && device.connection_status?.status === 'acquiring'"
                      size="small"
                      color="orange"
                      @click="stopDeviceAcquisition(device)"
                    >
                      <v-icon left>mdi-stop</v-icon>
                      停止采集
                    </v-btn>
                  </div>
                </template>
              </v-list-item>
              
              <v-list-item v-if="realDevices.length === 0">
                <v-list-item-title class="text-grey">
                  没有配置的真实设备
                </v-list-item-title>
                <v-list-item-subtitle>
                  请先添加可穿戴EEG设备
                </v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
    
    <!-- 添加设备对话框 -->
    <v-dialog v-model="showAddDeviceDialog" max-width="500">
      <v-card>
        <v-card-title>添加可穿戴EEG设备</v-card-title>
        <v-card-text>
          <v-form v-model="addDeviceFormValid" @submit.prevent="addRealDevice">
            <v-text-field
              v-model="newDevice.name"
              label="设备名称"
              :rules="[v => !!v || '设备名称不能为空']"
              required
              class="mb-3"
            />
            
            <v-select
              v-model="newDevice.port"
              :items="portOptions"
              label="串口端口"
              :rules="[v => !!v || '请选择串口端口']"
              required
              class="mb-3"
            >
              <template v-slot:item="{ props, item }">
                <v-list-item v-bind="props">
                  <template v-slot:prepend>
                    <v-icon :color="item.raw.is_ch340 ? 'green' : 'grey'">
                      {{ item.raw.is_ch340 ? 'mdi-chip' : 'mdi-usb-port' }}
                    </v-icon>
                  </template>
                  <v-list-item-title>
                    {{ item.raw.port }}
                    <v-chip v-if="item.raw.is_ch340" size="x-small" color="green" class="ml-1">
                      CH340
                    </v-chip>
                  </v-list-item-title>
                  <v-list-item-subtitle>{{ item.raw.description }}</v-list-item-subtitle>
                </v-list-item>
              </template>
            </v-select>
            
            <v-select
              v-model="newDevice.baudrate"
              :items="baudrateOptions"
              label="波特率"
              :rules="[v => !!v || '请选择波特率']"
              required
              class="mb-3"
            />
            
            <v-text-field
              v-model="newDevice.sampling_rate"
              label="采样率 (Hz)"
              type="number"
              :rules="[v => !!v || '采样率不能为空', v => v > 0 || '采样率必须大于0']"
              required
              class="mb-3"
            />
            
            <v-text-field
              v-model="newDevice.channel_count"
              label="通道数"
              type="number"
              :rules="[v => !!v || '通道数不能为空', v => v > 0 || '通道数必须大于0']"
              required
              class="mb-3"
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showAddDeviceDialog = false">取消</v-btn>
          <v-btn 
            color="primary" 
            @click="addRealDevice"
            :disabled="!addDeviceFormValid"
          >
            添加设备
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    
    <!-- 连接设备对话框 -->
    <v-dialog v-model="showConnectDialog" max-width="400">
      <v-card>
        <v-card-title>连接设备</v-card-title>
        <v-card-text>
          <p>连接到端口: <strong>{{ selectedPort?.port }}</strong></p>
          <p v-if="selectedPort?.description">设备描述: {{ selectedPort.description }}</p>
          
          <v-select
            v-model="connectBaudrate"
            :items="baudrateOptions"
            label="波特率"
            required
            class="mt-4"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showConnectDialog = false">取消</v-btn>
          <v-btn 
            color="primary" 
            @click="confirmConnect"
            :loading="realDeviceApi.isLoading.value"
          >
            连接
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { realDeviceApi, type SerialPort, type RealDeviceInfo } from '../services/realDeviceApi'
import { deviceApi } from '../services/deviceApi'

// 状态
const expandedPanels = ref([0, 1, 2])
const showAddDeviceDialog = ref(false)
const showConnectDialog = ref(false)
const addDeviceFormValid = ref(false)
const selectedPort = ref<SerialPort | null>(null)

// 新设备表单
const newDevice = ref({
  name: '可穿戴EEG设备',
  port: '',
  baudrate: 460800,
  sampling_rate: 1000,
  channel_count: 8
})

// 连接参数
const connectBaudrate = ref(460800)

// 计算属性
const portOptions = computed(() => {
  return realDeviceApi.ports.value.map(port => ({
    title: `${port.port}${port.is_ch340 ? ' (CH340)' : ''}`,
    value: port.port,
    ...port
  }))
})

const baudrateOptions = computed(() => {
  return realDeviceApi.getBaudrateOptions().map(rate => ({
    title: rate.toString(),
    value: rate
  }))
})

// 统一设备列表过滤
const allDevices = computed(() => {
  return realDeviceApi.devices.value
})

const realDevices = computed(() => {
  return realDeviceApi.devices.value.filter(device => device.type === 'wearable_eeg')
})

const connectedDevices = computed(() => {
  return realDeviceApi.devices.value.filter(device => 
    device.type === 'wearable_eeg' && 
    device.config.connected === true
  )
})

const simulatedDevices = computed(() => {
  return realDeviceApi.devices.value.filter(device => device.type === 'simulated')
})

// 方法
const scanPorts = async () => {
  await realDeviceApi.scanPorts()
}

const connectToPort = (port: SerialPort) => {
  selectedPort.value = port
  connectBaudrate.value = realDeviceApi.detectBestBaudrate(port)
  showConnectDialog.value = true
}

const confirmConnect = async () => {
  if (!selectedPort.value) return
  
  const result = await realDeviceApi.connectDevice(
    selectedPort.value.port,
    connectBaudrate.value
  )
  
  if (result) {
    showConnectDialog.value = false
    // 刷新设备列表
    await realDeviceApi.getDevices()
  }
}

const startAcquisition = async (port: string) => {
  await realDeviceApi.startAcquisition(port)
}

const stopAcquisition = async (port: string) => {
  await realDeviceApi.stopAcquisition(port)
}

const disconnectDevice = async (port: string) => {
  await realDeviceApi.disconnectDevice(port)
}

const addRealDevice = async () => {
  if (!addDeviceFormValid.value) return
  
  try {
    // 创建设备
    const deviceData = {
      name: newDevice.value.name,
      type: 'wearable_eeg' as const,
      sampling_rate: Number(newDevice.value.sampling_rate),
      channel_count: Number(newDevice.value.channel_count),
      config: {
        port: newDevice.value.port,
        baudrate: newDevice.value.baudrate,
        connected: false,
        acquiring: false
      }
    }
    
    const result = await deviceApi.createDevice(deviceData)
    
    if (result) {
      // 刷新设备列表
      await realDeviceApi.getDevices()
      showAddDeviceDialog.value = false
      
      // 重置表单
      newDevice.value = {
        name: '可穿戴EEG设备',
        port: '',
        baudrate: 460800,
        sampling_rate: 1000,
        channel_count: 8
      }
    }
  } catch (error) {
    console.error('Failed to add real device:', error)
  }
}

const connectDevice = async (device: RealDeviceInfo) => {
  if (!device.config.port) return
  
  const result = await realDeviceApi.connectDevice(
    device.config.port,
    device.config.baudrate || 460800,
    device.id
  )
  
  if (result) {
    await realDeviceApi.getDevices()
  }
}

const startDeviceAcquisition = async (device: RealDeviceInfo) => {
  if (!device.config.port) return
  
  const success = await realDeviceApi.startAcquisition(device.config.port)
  if (success) {
    await realDeviceApi.getDevices()
  }
}

const stopDeviceAcquisition = async (device: RealDeviceInfo) => {
  if (!device.config.port) return
  
  const success = await realDeviceApi.stopAcquisition(device.config.port)
  if (success) {
    await realDeviceApi.getDevices()
  }
}

const formatTime = (timestamp: number) => {
  const date = new Date(timestamp * 1000)
  return date.toLocaleTimeString()
}

// 生命周期
onMounted(async () => {
  // 初始化时加载数据
  await Promise.all([
    realDeviceApi.scanPorts(),
    realDeviceApi.getDevices()
  ])
})
</script>

<style scoped>
.border-primary {
  border-color: var(--v-primary-base) !important;
}

.bg-green-lighten-5 {
  background-color: rgba(76, 175, 80, 0.1) !important;
}
</style>