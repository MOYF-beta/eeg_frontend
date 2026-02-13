<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        波形可视化
        <v-tooltip location="bottom">
          <template #activator="{ props }">
            <v-icon v-bind="props" size="small" class="ml-2" color="info">
              mdi-information
            </v-icon>
          </template>
          <div>
            <div>数据源：{{ dataSourceText }}</div>
            <div v-if="targetNode">绑定节点: {{ targetNode.name }}</div>
            <div>数据点数: {{ totalSamples }}</div>
          </div>
        </v-tooltip>
      </div>

      <div class="d-flex align-center ga-2">
        <!-- 数据源选择 -->
        <v-select
          v-model="selectedNodeId"
          :items="availableOscNodes"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="选择数据源"
          style="width: 200px"
          class="mr-2"
          @update:model-value="onNodeSelected"
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

        <!-- 解除绑定按钮 -->
        <v-btn
          v-if="selectedNodeId"
          size="small"
          color="error"
          variant="text"
          @click="unbindNode"
        >
          解除绑定
        </v-btn>

        <v-chip size="small" :color="statusColor">
          <v-icon left size="small">{{ statusIcon }}</v-icon>
          {{ statusText }}
        </v-chip>

        <!-- 删除卡片按钮 -->
        <v-btn
          size="small"
          color="grey"
          variant="text"
          icon="mdi-close"
          @click="$emit('remove')"
        />
      </div>
    </v-card-title>

    <v-divider />

    <v-card-text>
      <!-- 未选择数据源提示 -->
      <v-alert v-if="!selectedNodeId" type="info" class="mb-4">
        请从上方下拉菜单选择计算图中的示波器节点作为数据源。
        <a href="#/cpgraph" target="_blank">前往计算图编辑器 →</a>
      </v-alert>

      <!-- 计算图未冻结提示 -->
      <v-alert v-else-if="!isGraphFrozen" type="warning" class="mb-4">
        计算图未冻结。请在<a href="#/cpgraph" target="_blank">计算图编辑器</a>中点击"冻结"按钮启动数据流。
      </v-alert>

      <div class="osc-root">
        <div class="osc-controls">
          <div class="control">
            <div class="control-label">显示模式</div>
            <v-select
              v-model="mode"
              :items="modeItems"
              density="compact"
              variant="outlined"
              hide-details
              :disabled="!canDisplay"
            />
          </div>
          <div class="control control-wide">
            <div class="control-label">时间窗口（秒）</div>
            <v-slider
              v-model="timeWindowSec"
              :min="1"
              :max="15"
              :step="1"
              density="compact"
              hide-details
              :disabled="!canDisplay"
            />
          </div>
          <div class="control">
            <div class="control-label">数据状态</div>
            <div class="text-body-2">
              <div>接收: {{ packetCount }} 包</div>
              <div>缓存: {{ totalSamples }} 点</div>
            </div>
          </div>
        </div>

        <div class="osc-chart-container">
          <!-- ECharts 容器 -->
          <div ref="chartRef" class="osc-chart"></div>
          
          <!-- 无数据遮罩 -->
          <div v-if="!canDisplay" class="no-data-overlay">
            <v-icon size="48" color="grey-lighten-1">mdi-waveform</v-icon>
            <div class="text-h6 mt-2">{{ noDataText }}</div>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import * as echarts from 'echarts';
import { sessionStore } from '../services/sessionStore';
import { eegWebSocket, type EegDataPacket } from '../services/websocket';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';

const props = defineProps<{
  initialNodeId?: string;
}>();

const emit = defineEmits<{
  (e: 'remove'): void;
}>();

// 配置
const channelCount = 8;
const colors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];

// 状态
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
const mode = ref<'scan' | 'scroll'>('scroll');
const timeWindowSec = ref(5);

// 数据存储 - 使用环形缓冲区
const MAX_SAMPLES = 50000; // 最大缓存5万点 (50秒@1000Hz)
const samples: number[][] = Array.from({ length: channelCount }, () => []);
const timestamps: number[] = [];

// 数据源
const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);

// WebSocket 状态
const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

// 计算属性
const modeItems = [
  { title: '扫描', value: 'scan' },
  { title: '滚动', value: 'scroll' },
];

const availableOscNodes = computed(() => {
  return graphNodes.value.filter(n => n.type === 'OSC');
});

const targetNode = computed(() => {
  if (!selectedNodeId.value) return null;
  return graphNodes.value.find(n => n.id === selectedNodeId.value);
});

const canDisplay = computed(() => {
  return selectedNodeId.value && isGraphFrozen.value && wsStatus.value === 'connected';
});

const dataSourceText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  const node = targetNode.value;
  return node ? node.name : selectedNodeId.value;
});

const statusText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  if (!isGraphFrozen.value) return '未冻结';
  switch (wsStatus.value) {
    case 'connected':
      return packetCount.value > 0 ? '接收中' : '等待数据';
    case 'connecting':
      return '连接中';
    case 'error':
      return '错误';
    default:
      return '未连接';
  }
});

const statusColor = computed(() => {
  if (!selectedNodeId.value) return 'grey';
  if (!isGraphFrozen.value) return 'warning';
  switch (wsStatus.value) {
    case 'connected':
      return packetCount.value > 0 ? 'success' : 'info';
    case 'connecting':
      return 'info';
    case 'error':
      return 'error';
    default:
      return 'grey';
  }
});

const statusIcon = computed(() => {
  switch (statusColor.value) {
    case 'success':
      return 'mdi-check-circle';
    case 'warning':
      return 'mdi-alert';
    case 'error':
      return 'mdi-alert-circle';
    case 'info':
      return 'mdi-sync';
    default:
      return 'mdi-minus-circle';
  }
});

const noDataText = computed(() => {
  if (!selectedNodeId.value) return '请选择数据源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  if (wsStatus.value !== 'connected') return '等待连接';
  return '等待数据';
});

const totalSamples = computed(() => timestamps.length);

// 方法
const isNodeBound = (nodeId: string) => {
  return false;
};

const onNodeSelected = (nodeId: string | null) => {
  if (nodeId) {
    sessionStore.bindOscilloscope('osc-' + Date.now(), nodeId);
    subscribeToNode(nodeId);
  }
};

const unbindNode = () => {
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  selectedNodeId.value = null;
};

const subscribeToNode = (nodeId: string) => {
  if (isGraphFrozen.value) {
    eegWebSocket.subscribe([nodeId]);
  }
};

// 初始化 ECharts
const initChart = () => {
  if (!chartRef.value) return;
  
  chart = echarts.init(chartRef.value);
  
  const option: echarts.EChartsOption = {
    backgroundColor: '#fff',
    grid: {
      left: 60,
      right: 20,
      top: 30,
      bottom: 60,
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
      },
    },
    legend: {
      data: Array.from({ length: channelCount }, (_, i) => `CH${i + 1}`),
      top: 5,
      textStyle: {
        fontSize: 11,
      },
    },
    xAxis: {
      type: 'value',
      name: '时间 (ms)',
      nameLocation: 'middle',
      nameGap: 30,
      min: 0,
      max: timeWindowSec.value * 1000,
    },
    yAxis: {
      type: 'value',
      name: '幅值 (μV)',
      nameLocation: 'middle',
      nameGap: 40,
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        start: 0,
        end: 100,
      },
      {
        type: 'slider',
        xAxisIndex: 0,
        start: 0,
        end: 100,
        height: 20,
        bottom: 10,
      },
    ],
    series: Array.from({ length: channelCount }, (_, i) => ({
      name: `CH${i + 1}`,
      type: 'line',
      smooth: false,
      symbol: 'none',
      sampling: 'lttb', // 使用 LTTB 降采样算法
      itemStyle: {
        color: colors[i],
      },
      lineStyle: {
        width: 1,
      },
      data: [],
    })),
  };
  
  chart.setOption(option);
  
  // 响应窗口大小变化
  const handleResize = () => chart?.resize();
  window.addEventListener('resize', handleResize);
  
  return () => {
    window.removeEventListener('resize', handleResize);
  };
};

// 更新图表数据
const updateChart = () => {
  if (!chart || samples[0].length === 0) return;
  
  // 构建数据点
  const seriesData = samples.map((channelData, chIdx) => {
    return channelData.map((value, idx) => [timestamps[idx], value + chIdx * 100]); // 通道分离显示
  });
  
  const option: echarts.EChartsOption = {
    xAxis: {
      min: mode.value === 'scroll' 
        ? Math.max(0, (timestamps[timestamps.length - 1] || 0) - timeWindowSec.value * 1000)
        : 0,
      max: mode.value === 'scroll'
        ? (timestamps[timestamps.length - 1] || timeWindowSec.value * 1000)
        : timeWindowSec.value * 1000,
    },
    series: seriesData.map((data, i) => ({
      data: data,
    })),
  };
  
  chart.setOption(option);
};

// WebSocket 数据处理器
const handleDataPacket = (packet: EegDataPacket) => {
  if (packet.nodeId !== selectedNodeId.value) return;
  
  packetCount.value++;
  
  // 添加时间戳（相对于第一个包的时间）
  if (timestamps.length === 0) {
    timestamps.push(0);
  } else {
    const lastTime = timestamps[timestamps.length - 1];
    timestamps.push(lastTime + 1); // 1ms间隔（1000Hz）
  }
  
  // 添加通道数据
  for (let ch = 0; ch < channelCount && ch < packet.channels.length; ch++) {
    samples[ch].push(packet.channels[ch]);
  }
  
  // 环形缓冲区：移除旧数据
  if (timestamps.length > MAX_SAMPLES) {
    timestamps.shift();
    for (let ch = 0; ch < channelCount; ch++) {
      samples[ch].shift();
    }
  }
  
  // 每100ms更新一次图表（约100个样本）
  if (packetCount.value % 100 === 0) {
    updateChart();
  }
};

// 更新计算图状态
const updateGraphState = async () => {
  try {
    const graph = await fetchGraph();
    graphNodes.value = graph.nodes || [];
    isGraphFrozen.value = graph.frozen || false;
    
    if (isGraphFrozen.value && selectedNodeId.value) {
      subscribeToNode(selectedNodeId.value);
    }
  } catch (e) {
    console.error('Failed to fetch graph:', e);
  }
};

// 生命周期
onMounted(() => {
  // 初始化 ECharts
  const cleanup = initChart();
  
  // 加载计算图状态
  updateGraphState();
  
  // 注册WebSocket回调
  eegWebSocket.onConnected = () => {
    wsStatus.value = 'connected';
    if (selectedNodeId.value && isGraphFrozen.value) {
      subscribeToNode(selectedNodeId.value);
    }
  };
  eegWebSocket.onDisconnected = () => {
    wsStatus.value = 'disconnected';
  };
  eegWebSocket.onData = handleDataPacket;
  
  // 如果WebSocket已连接，更新状态
  if (eegWebSocket.isConnected()) {
    wsStatus.value = 'connected';
  }
  
  onUnmounted(() => {
    cleanup?.();
    chart?.dispose();
    if (selectedNodeId.value) {
      eegWebSocket.unsubscribe([selectedNodeId.value]);
    }
  });
});

// 监听选中节点变化
watch(selectedNodeId, (newId, oldId) => {
  if (oldId) {
    eegWebSocket.unsubscribe([oldId]);
  }
  if (newId && isGraphFrozen.value) {
    subscribeToNode(newId);
  }
});

// 监听时间窗口变化
watch(timeWindowSec, () => {
  updateChart();
});

// 监听模式变化
watch(mode, () => {
  updateChart();
});
</script>

<style scoped>
.osc-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.osc-controls {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.control {
  min-width: 120px;
}

.control-wide {
  flex: 1;
  min-width: 200px;
}

.control-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.osc-chart-container {
  position: relative;
  height: 400px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
}

.osc-chart {
  width: 100%;
  height: 100%;
}

.no-data-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
}
</style>
