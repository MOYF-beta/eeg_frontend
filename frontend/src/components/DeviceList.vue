<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      设备列表
      <div class="d-flex align-center ga-2">
        <v-btn color="primary" size="small" @click="refreshDevices">
          <v-icon left>mdi-refresh</v-icon>
          刷新
        </v-btn>
        <v-btn color="secondary" size="small" @click="showAddDialog = true">
          <v-icon left>mdi-plus</v-icon>
          添加设备
        </v-btn>
      </div>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <v-row>
        <v-col
          v-for="device in devices"
          :key="device.id"
          cols="12"
          md="6"
        >
          <v-card variant="outlined" :class="{ 'border-primary': device.status === 'online' }">
            <v-card-title class="d-flex align-center">
              <v-icon :color="device.status === 'online' ? 'green' : 'grey'" class="mr-2">
                {{ device.status === 'online' ? 'mdi-checkbox-blank-circle' : 'mdi-checkbox-blank-circle-outline' }}
              </v-icon>
              {{ device.name }}
              <v-spacer />
              <v-chip size="small" :color="device.status === 'online' ? 'success' : 'grey'">
                {{ device.status === 'online' ? '在线' : '离线' }}
              </v-chip>
            </v-card-title>
            <v-card-subtitle>
              地址: {{ device.port || device.address || 'N/A' }}
            </v-card-subtitle>
            <v-card-text class="text-body-2">
              <div>采样率: {{ device.sampleRate }}Hz</div>
              <div>通道数: {{ device.channels }}{{ Array.isArray(device.channels) ? '通道' : 'ch' }}</div>
              
              <!-- 显示绑定状态 -->
              <v-divider class="my-2" />
              <div class="d-flex align-center">
                <span class="text-caption mr-2">绑定状态:</span>
                <v-chip
                  v-if="getBoundNode(device.id)"
                  size="small"
                  color="success"
                  class="mr-2"
                >
                  <v-icon size="small" class="mr-1">mdi-link</v-icon>
                  {{ getBoundNode(device.id)?.name }}
                </v-chip>
                <v-chip v-else size="small" color="grey">
                  <v-icon size="small" class="mr-1">mdi-link-off</v-icon>
                  未绑定
                </v-chip>
                <span class="text-caption text-grey">
                  {{ getBoundNode(device.id) ? '在计算图中绑定' : '在计算图编辑器中绑定设备' }}
                </span>
              </div>
            </v-card-text>
            <v-card-actions>
              <v-btn size="small" variant="text" @click="editDevice(device)">
                编辑
              </v-btn>
              <v-spacer />
              <v-btn 
                size="small" 
                color="error" 
                variant="text"
                @click="deleteDevice(device.id)"
              >
                删除
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>

      <!-- 空状态 -->
      <v-alert v-if="devices.length === 0" type="info" class="mt-4">
        暂无设备。点击"添加设备"按钮添加新设备。
      </v-alert>

      <!-- 绑定说明 -->
      <v-alert type="info" class="mt-4" variant="tonal">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-information</v-icon>
          <span>
            设备绑定已移至
            <router-link to="/cpgraph">计算图编辑器</router-link>
            。在编辑 SOURCE 节点时选择绑定的设备。
          </span>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>

  <!-- 添加/编辑设备对话框 -->
  <v-dialog v-model="showAddDialog" max-width="500">
    <v-card>
      <v-card-title>{{ editingDevice ? '编辑设备' : '添加设备' }}</v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <v-text-field
          v-model="deviceForm.name"
          label="设备名称"
          density="compact"
          variant="outlined"
          class="mb-3"
        />
        <v-select
          v-model="deviceForm.type"
          :items="['simulated', 'serial', 'network']"
          label="设备类型"
          density="compact"
          variant="outlined"
          class="mb-3"
        />
        <v-text-field
          v-model="deviceForm.address"
          label="地址/端口"
          density="compact"
          variant="outlined"
          class="mb-3"
          placeholder="如: COM3 或 192.168.1.100:8080"
        />
        <v-text-field
          v-model.number="deviceForm.sampleRate"
          label="采样率 (Hz)"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
        />
        <v-text-field
          v-model.number="deviceForm.channels"
          label="通道数"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
        />

        <!-- 模拟设备配置 -->
        <div v-if="deviceForm.type === 'simulated'">
          <v-expansion-panels class="mb-3">
            <v-expansion-panel>
              <v-expansion-panel-title>
                <v-icon left>mdi-cog</v-icon>
                模拟设备配置
              </v-expansion-panel-title>
              <v-expansion-panel-text>
                <simulated-device-config-component
                  v-model="deviceForm.simulatedConfig"
                  :channel-count="deviceForm.channels"
                  :show-global-noise="true"
                />
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-btn variant="text" @click="closeDialog">取消</v-btn>
        <v-spacer />
        <v-btn color="primary" @click="saveDevice">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import { sessionStore, type Device, type SimulatedDeviceConfig } from '../services/sessionStore';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';
import SimulatedDeviceConfigComponent from './SimulatedDeviceConfig.vue';
import { deviceApi } from '../services/deviceApi';

// 本地状态
const devices = ref<Device[]>([]);
const graphNodes = ref<GraphNode[]>([]);
const showAddDialog = ref(false);
const editingDevice = ref<Device | null>(null);

const deviceForm = ref({
  name: '',
  type: 'simulated',
  address: '',
  sampleRate: 1000,
  channels: 8,
  simulatedConfig: {
    channels: [],
    globalNoise: {
      type: 'none',
      amplitude: 0
    }
  } as SimulatedDeviceConfig
});

// 计算属性：获取绑定到此设备的节点
const getBoundNode = (deviceId: string): GraphNode | undefined => {
  return graphNodes.value.find(node => 
    node.type === 'SOURCE' && (node.deviceId === deviceId || node.params?.deviceId === deviceId)
  );
};

// 刷新设备列表
async function refreshDevices() {
  try {
    // 从后端API获取设备列表
    const apiDevices = await deviceApi.getDevices();
    
    // 转换API设备格式为前端格式
    const convertedDevices: Device[] = apiDevices.map(apiDevice => {
      const device: Device = {
        id: apiDevice.id,
        name: apiDevice.name,
        status: 'online', // 默认在线状态
        sampleRate: apiDevice.sampling_rate || 1000,
        channels: apiDevice.channel_count || 8,
        port: apiDevice.address,
        address: apiDevice.address,
        type: apiDevice.type as 'simulated' | 'physical'
      };
      
      // 如果有配置，转换配置格式
      if (apiDevice.config) {
        device.config = deviceApi.convertFromApiConfig(apiDevice.config);
      }
      
      return device;
    });
    
    if (convertedDevices.length > 0) {
      devices.value = convertedDevices;
      sessionStore.setDevices(convertedDevices);
    } else {
      // 如果没有设备，使用默认模拟设备
      loadDefaultDevices();
    }
  } catch (error) {
    console.error('Failed to fetch devices from API:', error);
    // 如果API失败，回退到本地存储
    const storedDevices = sessionStore.getDevices();
    if (storedDevices.length > 0) {
      devices.value = storedDevices;
    } else {
      loadDefaultDevices();
    }
  }
  
  // 同时刷新计算图节点
  await loadGraphNodes();
}

// 加载计算图节点
async function loadGraphNodes() {
  try {
    const payload = await fetchGraph();
    graphNodes.value = payload.nodes;
    // 同时更新 sessionStore
    sessionStore.setGraph(payload);
  } catch (err) {
    console.error('Failed to load graph nodes:', err);
    // 从 sessionStore 获取
    graphNodes.value = sessionStore.getGraph().nodes;
  }
}

// 加载默认设备
function loadDefaultDevices() {
  const defaultDevices: Device[] = [
    {
      id: 'mock-1',
      name: '模拟设备 1',
      status: 'online',
      sampleRate: 1000,
      channels: 8,
      port: 'COM3',
      address: 'SIM-001',
      type: 'simulated',
      config: {
        channels: Array.from({ length: 8 }, (_, index) => ({
          index,
          enabled: true,
          signal: {
            type: 'sine',
            frequency: 10 + index * 2, // 不同频率
            amplitude: 100,
            phase: 0
          },
          noise: {
            type: 'white',
            amplitude: 5
          }
        })),
        globalNoise: {
          type: 'none',
          amplitude: 0
        }
      }
    },
  ];
  
  devices.value = defaultDevices;
  sessionStore.setDevices(defaultDevices);
}

// 编辑设备
function editDevice(device: Device) {
  editingDevice.value = device;
  deviceForm.value = {
    name: device.name,
    type: 'simulated',
    address: device.port || device.address || '',
    sampleRate: device.sampleRate,
    channels: device.channels,
    simulatedConfig: device.config || {
      channels: [],
      globalNoise: {
        type: 'none',
        amplitude: 0
      }
    }
  };
  showAddDialog.value = true;
}

// 删除设备
async function deleteDevice(deviceId: string) {
  if (!confirm('确定要删除此设备吗？')) return;
  
  try {
    await deviceApi.deleteDevice(deviceId);
    devices.value = devices.value.filter(d => d.id !== deviceId);
    sessionStore.setDevices(devices.value);
  } catch (error) {
    console.error('Failed to delete device:', error);
    alert(`删除设备失败: ${error instanceof Error ? error.message : '未知错误'}`);
  }
}

// 关闭对话框
function closeDialog() {
  showAddDialog.value = false;
  editingDevice.value = null;
  deviceForm.value = {
    name: '',
    type: 'simulated',
    address: '',
    sampleRate: 1000,
    channels: 8,
    simulatedConfig: {
      channels: [],
      globalNoise: {
        type: 'none',
        amplitude: 0
      }
    }
  };
}

// 保存设备
async function saveDevice() {
  try {
    if (editingDevice.value) {
      // 编辑现有设备
      const updates = {
        name: deviceForm.value.name,
        sampling_rate: deviceForm.value.sampleRate,
        channel_count: deviceForm.value.channels,
        address: deviceForm.value.address,
        config: deviceForm.value.type === 'simulated' ? 
          deviceApi.convertToApiConfig(deviceForm.value.simulatedConfig) : undefined
      };
      
      const updatedDevice = await deviceApi.updateDevice(editingDevice.value.id, updates);
      
      // 更新本地设备列表
      const index = devices.value.findIndex(d => d.id === editingDevice.value!.id);
      if (index !== -1) {
        devices.value[index] = {
          ...devices.value[index],
          ...updatedDevice,
          config: deviceForm.value.type === 'simulated' ? deviceForm.value.simulatedConfig : undefined
        };
      }
    } else {
      // 添加新设备
      const deviceData = {
        type: deviceForm.value.type as 'simulated' | 'physical',
        name: deviceForm.value.name || `设备 ${devices.value.length + 1}`,
        address: deviceForm.value.address || 'SIM-001',
        sampling_rate: deviceForm.value.sampleRate,
        channel_count: deviceForm.value.channels,
        config: deviceForm.value.type === 'simulated' ? 
          deviceApi.convertToApiConfig(deviceForm.value.simulatedConfig) : undefined
      };
      
      const newDevice = await deviceApi.createDevice(deviceData);
      
      // 添加配置到新设备
      const deviceWithConfig: Device = {
        ...newDevice,
        config: deviceForm.value.type === 'simulated' ? deviceForm.value.simulatedConfig : undefined
      };
      
      devices.value.push(deviceWithConfig);
    }
    
    sessionStore.setDevices(devices.value);
    closeDialog();
  } catch (error) {
    console.error('Failed to save device:', error);
    alert(`保存设备失败: ${error instanceof Error ? error.message : '未知错误'}`);
  }
}

// 监听 sessionStore 变化
let unsubscribe: (() => void) | null = null;

onMounted(() => {
  refreshDevices();
  
  // 订阅 sessionStore 变化
  unsubscribe = sessionStore.subscribe((state) => {
    if (state.devices.length > 0) {
      devices.value = state.devices;
    }
    if (state.graph.nodes.length > 0) {
      graphNodes.value = state.graph.nodes;
    }
  });
});

// 清理
onUnmounted(() => {
  if (unsubscribe) {
    unsubscribe();
  }
});
</script>

<style scoped>
.border-primary {
  border-color: rgb(var(--v-theme-primary)) !important;
  border-width: 2px !important;
}
</style>
