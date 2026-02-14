<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      设备列表
      <div class="d-flex align-center ga-2">
        <v-btn color="primary" size="small" @click="refreshDevices">
          <v-icon left>mdi-refresh</v-icon>
          刷新
        </v-btn>
        <v-btn color="secondary" size="small" @click="addMockDevice">
          添加模拟设备
        </v-btn>
      </div>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <!-- 计算图状态提示 -->
      <v-alert v-if="graphNodes.length === 0" type="info" class="mb-4">
        计算图中没有输入节点。请先在<router-link to="/cpgraph">计算图编辑器</router-link>中添加数据源节点。
      </v-alert>
      
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
              地址: {{ device.port || device.address }}
            </v-card-subtitle>
            <v-card-text class="text-body-2">
              <div>采样率: {{ device.sampleRate }}Hz</div>
              <div>通道数: {{ device.channels }}{{ Array.isArray(device.channels) ? '通道' : 'ch' }}</div>
              
              <!-- 计算图节点绑定 -->
              <v-divider class="my-2" />
              <div class="d-flex align-center">
                <span class="text-caption mr-2">绑定计算图节点:</span>
                <v-select
                  v-model="nodeBindings[device.id]"
                  :items="availableSourceNodes"
                  item-title="name"
                  item-value="id"
                  density="compact"
                  variant="outlined"
                  hide-details
                  placeholder="选择输入节点"
                  class="flex-grow-1"
                  @update:model-value="(val) => bindNode(device.id, val)"
                >
                  <template #item="{ props, item }">
                    <v-list-item v-bind="props">
                      <template #append>
                        <v-chip v-if="isNodeBound(item.raw.id)" size="x-small" color="primary">
                          已绑定
                        </v-chip>
                      </template>
                    </v-list-item>
                  </template>
                </v-select>
              </div>
              <div v-if="nodeBindings[device.id]" class="mt-1">
                <v-chip size="x-small" color="success">
                  已绑定到: {{ getNodeName(nodeBindings[device.id]) }}
                </v-chip>
              </div>
            </v-card-text>
            <v-card-actions>
              <v-btn size="small" variant="text" @click="viewDevice(device.id)">
                查看详情
              </v-btn>
              <v-spacer />
              <v-btn 
                size="small" 
                color="error" 
                variant="text"
                @click="unbindNode(device.id)"
                :disabled="!nodeBindings[device.id]"
              >
                解除绑定
              </v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
      
      <!-- 未绑定设备提示 -->
      <v-alert v-if="unboundSourceNodes.length > 0" type="warning" class="mt-4">
        <div class="d-flex align-center">
          <span>以下计算图输入节点未绑定设备：</span>
          <v-chip
            v-for="node in unboundSourceNodes"
            :key="node.id"
            size="small"
            class="mx-1"
          >
            {{ node.name }}
          </v-chip>
        </div>
      </v-alert>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { sessionStore, type Device } from '../services/sessionStore';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';

// 本地状态
const devices = ref<Device[]>([]);
const graphNodes = ref<GraphNode[]>([]);
const nodeBindings = ref<Record<string, string>>({}); // deviceId -> nodeId

// 计算属性：可用的 SOURCE 节点
const availableSourceNodes = computed(() => {
  return graphNodes.value.filter(n => n.type === 'SOURCE');
});

// 计算属性：未绑定的 SOURCE 节点
const unboundSourceNodes = computed(() => {
  const boundNodeIds = Object.values(nodeBindings.value);
  return availableSourceNodes.value.filter(n => !boundNodeIds.includes(n.id));
});

// 检查节点是否已被其他设备绑定
function isNodeBound(nodeId: string): boolean {
  return Object.values(nodeBindings.value).includes(nodeId);
}

// 获取节点名称
function getNodeName(nodeId: string): string {
  const node = graphNodes.value.find(n => n.id === nodeId);
  return node?.name || nodeId;
}

// 绑定设备到节点
function bindNode(deviceId: string, nodeId: string | null) {
  if (!nodeId) {
    sessionStore.unbindInputNode(nodeBindings.value[deviceId]);
    delete nodeBindings.value[deviceId];
    return;
  }
  
  // 检查节点是否已被其他设备绑定
  const existingDevice = Object.entries(nodeBindings.value)
    .find(([_, nid]) => nid === nodeId);
  
  if (existingDevice && existingDevice[0] !== deviceId) {
    // 解除之前的绑定
    const oldDeviceId = existingDevice[0];
    delete nodeBindings.value[oldDeviceId];
  }
  
  // 建立新的绑定
  sessionStore.bindInputNode(nodeId, deviceId);
  nodeBindings.value[deviceId] = nodeId;
}

// 解除绑定
function unbindNode(deviceId: string) {
  const nodeId = nodeBindings.value[deviceId];
  if (nodeId) {
    sessionStore.unbindInputNode(nodeId);
    delete nodeBindings.value[deviceId];
  }
}

// 查看设备详情
function viewDevice(id: string) {
  console.log('View device:', id);
  // TODO: 打开设备详情对话框
}

// 刷新设备列表
async function refreshDevices() {
  // 从 sessionStore 获取设备列表
  const storedDevices = sessionStore.getDevices();
  if (storedDevices.length > 0) {
    devices.value = storedDevices;
  } else {
    // 如果没有存储的设备，使用默认模拟设备
    loadDefaultDevices();
  }
  
  // 同时刷新计算图节点
  await loadGraphNodes();
  
  // 同步绑定关系
  syncBindings();
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

// 同步绑定关系
function syncBindings() {
  const mappings = sessionStore.getInputMappings();
  nodeBindings.value = {};
  
  // 反转映射：nodeId -> deviceId 转为 deviceId -> nodeId
  Object.entries(mappings).forEach(([nodeId, deviceId]) => {
    if (devices.value.find(d => d.id === deviceId)) {
      nodeBindings.value[deviceId] = nodeId;
    }
  });
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
    },
  ];
  
  devices.value = defaultDevices;
  sessionStore.setDevices(defaultDevices);
}

// 添加模拟设备
function addMockDevice() {
  const newId = `mock-${devices.value.length + 1}`;
  const newDevice: Device = {
    id: newId,
    name: `模拟设备 ${devices.value.length + 1}`,
    status: 'online',
    sampleRate: 1000,
    channels: 8,
    port: `COM${devices.value.length + 3}`,
  };
  
  devices.value.push(newDevice);
  sessionStore.setDevices(devices.value);
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
    syncBindings();
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