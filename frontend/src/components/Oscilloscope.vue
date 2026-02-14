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
            <div>总数据点数: {{ totalSamples }}</div>
            <div>窗口大小: {{ timeWindowSec }}s</div>
            <div>采样率: 1000Hz</div>
            <div>模式: 扫描模式</div>
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
        <router-link to="/cpgraph" target="_blank">前往计算图编辑器 →</router-link>
      </v-alert>

      <!-- 计算图未冻结提示 -->
      <v-alert v-else-if="!isGraphFrozen" type="warning" class="mb-4">
        计算图未冻结。请在<router-link to="/cpgraph" target="_blank">计算图编辑器</router-link>中点击"冻结"按钮启动数据流。
      </v-alert>

      <div class="osc-root">
        <div class="osc-controls">
          <div class="control">
            <div class="control-label">增益</div>
            <v-slider
              v-model="gain"
              :min="0.5"
              :max="3"
              :step="0.1"
              density="compact"
              hide-details
              :disabled="!canDisplay"
            />
          </div>
          <div class="control">
            <div class="control-label">时间窗口</div>
            <v-slider
              v-model="timeWindowSec"
              :min="1"
              :max="10"
              :step="1"
              density="compact"
              hide-details
              :disabled="!canDisplay"
              thumb-label
            />
          </div>
          <div class="control">
            <div class="control-label">数据状态</div>
            <div class="text-body-2">
              <div>接收: {{ packetCount }} 包</div>
              <div>扫描位置: {{ scanPositionDisplay }} / {{ timeWindowSec * 1000 }}</div>
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

        <!-- 扫描模式说明 -->
        <div v-if="canDisplay" class="scan-mode-info">
          <v-alert type="info" density="compact" variant="tonal">
            <v-icon size="small" class="mr-1">mdi-information</v-icon>
            扫描模式：橙色扫描线从左到右移动，左侧为新数据，右侧为旧数据
          </v-alert>
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

// === 扫描模式配置 ===
const SAMPLE_RATE = 1000;
const DEFAULT_WINDOW_SEC = 5;
const MAX_WINDOW_SEC = 10;
const BUFFER_SIZE = MAX_WINDOW_SEC * SAMPLE_RATE; // 最大10秒缓冲区

// 性能优化：目标刷新率 30fps
const TARGET_FPS = 30;
const FRAME_INTERVAL = 1000 / TARGET_FPS;

let lastFrameTime = 0;
let isFramePending = false;

// 状态
const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
const timeWindowSec = ref(DEFAULT_WINDOW_SEC);
const gain = ref(1);

// === 扫描模式数据存储 ===
// 固定大小的循环缓冲区，scanPos 指向当前写入位置（扫描线位置）
const samples: number[][] = Array.from({ length: channelCount }, () => new Array(BUFFER_SIZE).fill(0));
let scanPosition = 0; // 扫描线位置（0 ~ windowSize-1）
let isWrapped = false; // 是否已完成至少一次完整扫描
let totalReceivedSamples = 0;

// 数据源
const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);

// WebSocket 状态
const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

// 计算属性
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

// 数据点统计
const cachedSamples = computed(() => isWrapped ? BUFFER_SIZE : scanPosition);
const totalSamples = computed(() => totalReceivedSamples);

// 扫描位置显示（响应式）
const scanPositionDisplay = computed(() => scanPosition);

const noDataText = computed(() => {
  if (!selectedNodeId.value) return '请选择数据源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  if (wsStatus.value !== 'connected') return '等待连接';
  return '等待数据';
});

// 方法
const viewId = 'osc-view-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

const isNodeBound = (nodeId: string) => {
  return false;
};

const onNodeSelected = (nodeId: string | null) => {
  console.log('[Oscilloscope] Node selected:', nodeId, 'viewId:', viewId);
  if (nodeId) {
    sessionStore.bindViewToNode(viewId, nodeId);
    subscribeToNode(nodeId);
  } else {
    sessionStore.bindViewToNode(viewId, null);
  }
};

const unbindNode = () => {
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  sessionStore.bindViewToNode(viewId, null);
  selectedNodeId.value = null;
  // 清空数据
  scanPosition = 0;
  isWrapped = false;
  totalReceivedSamples = 0;
  samples.forEach(s => s.fill(0));
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
      bottom: 30,
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
      nameGap: 25,
      min: 0,
      max: timeWindowSec.value * 1000,
    },
    yAxis: {
      type: 'value',
      name: '幅值 (μV)',
      nameLocation: 'middle',
      nameGap: 40,
    },
    series: Array.from({ length: channelCount }, (_, i) => ({
      name: `CH${i + 1}`,
      type: 'line',
      smooth: false,
      symbol: 'none',
      sampling: 'lttb',
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

  const handleResize = () => chart?.resize();
  window.addEventListener('resize', handleResize);

  return () => {
    window.removeEventListener('resize', handleResize);
  };
};

// 更新图表 - 扫描模式
const updateChart = () => {
  if (!chart) return;

  const windowSize = timeWindowSec.value * SAMPLE_RATE;
  
  // 构建数据点
  // 扫描模式下：x轴 0~windowSize，scanPosition 处是扫描线
  // scanPosition 左侧是新数据（刚写入），右侧是旧数据
  const seriesData = [];
  
  for (let ch = 0; ch < channelCount; ch++) {
    const channelData = [];
    
    // 从 scanPosition 向左填充数据（新数据在左侧）
    for (let i = 0; i < windowSize; i++) {
      // x 坐标：0 是最新数据，windowSize 是最旧数据
      const x = i;
      
      // 从 scanPosition 往回数 i 个点
      let bufferIdx = scanPosition - 1 - i;
      if (bufferIdx < 0) {
        if (isWrapped) {
          bufferIdx += windowSize;
        } else {
          // 数据还不够，填0
          bufferIdx = -1;
        }
      }
      
      let value = 0;
      if (bufferIdx >= 0) {
        value = samples[ch][bufferIdx] || 0;
      }
      
      channelData.push([x, value * gain.value + ch * 80]);
    }
    
    // 反转数据，使新数据在左侧
    channelData.reverse();
    seriesData.push(channelData);
  }

  // 扫描线位置（在 x 轴上的位置）
  const scanLineX = Math.min(scanPosition, windowSize - 1);

  const option: echarts.EChartsOption = {
    xAxis: {
      min: 0,
      max: timeWindowSec.value * 1000,
      axisLabel: {
        formatter: (value: number) => {
          // 标签：0 是最新数据，右侧是旧数据
          const ageMs = value;
          if (ageMs === 0) return '现在';
          return `-${(ageMs / 1000).toFixed(1)}s`;
        }
      }
    },
    series: seriesData.map((data, i) => ({
      name: `CH${i + 1}`,
      type: 'line',
      smooth: false,
      symbol: 'none',
      sampling: 'lttb',
      itemStyle: { color: colors[i] },
      lineStyle: { width: 1 },
      data: data,
      markLine: i === 0 ? {
        symbol: ['none', 'none'],
        label: { show: false },
        lineStyle: {
          color: '#ff5722',
          width: 2,
          type: 'solid'
        },
        data: [
          { xAxis: scanLineX }
        ]
      } : undefined
    })),
  };

  chart.setOption(option, { replaceMerge: ['series'] });
};

// WebSocket 数据处理器
const handleDataPacket = (packet: EegDataPacket) => {
  // 宽松匹配：支持字符串和数字类型的 nodeId
  const packetNodeId = String(packet.nodeId);
  const selectedId = selectedNodeId.value ? String(selectedNodeId.value) : null;
  
  if (!selectedId || packetNodeId !== selectedId) return;

  packetCount.value++;

  const windowSize = timeWindowSec.value * SAMPLE_RATE;

  // 添加通道数据到扫描缓冲区
  for (let ch = 0; ch < channelCount && ch < packet.channels.length; ch++) {
    samples[ch][scanPosition] = packet.channels[ch];
  }
  
  // 移动扫描位置
  scanPosition++;
  totalReceivedSamples++;
  
  // 到达最右端，回到最左端重新开始
  if (scanPosition >= windowSize) {
    scanPosition = 0;
    isWrapped = true;
  }

  // 请求渲染帧（30fps节流）
  requestRenderFrame();
};

// 渲染循环：使用 requestAnimationFrame 实现 30fps
const requestRenderFrame = () => {
  if (isFramePending) return;
  isFramePending = true;

  requestAnimationFrame(() => {
    isFramePending = false;
    const now = performance.now();
    const elapsed = now - lastFrameTime;

    if (elapsed >= FRAME_INTERVAL) {
      lastFrameTime = now - (elapsed % FRAME_INTERVAL);
      updateChart();
    }
  });
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

// 清理函数
let cleanupChart: (() => void) | null = null;
let unsubConnected: (() => void) | null = null;
let unsubData: (() => void) | null = null;

console.log('[Oscilloscope] Component code loaded - v5 scan sweep mode');

// 生命周期
onMounted(async () => {
  try {
    cleanupChart = initChart();

    await updateGraphState();

    unsubConnected = eegWebSocket.onStatusChange((status) => {
      if (status === 'connected') {
        wsStatus.value = 'connected';
        if (selectedNodeId.value && isGraphFrozen.value) {
          subscribeToNode(selectedNodeId.value);
        }
      } else if (status === 'disconnected') {
        wsStatus.value = 'disconnected';
      }
    });
    unsubData = eegWebSocket.onData(handleDataPacket);

    if (eegWebSocket.isConnected()) {
      wsStatus.value = 'connected';
      if (selectedNodeId.value && isGraphFrozen.value) {
        subscribeToNode(selectedNodeId.value);
      }
    } else if (isGraphFrozen.value) {
      eegWebSocket.connect();
    }
  } catch (err) {
    console.error('[Oscilloscope] Error in onMounted:', err);
  }
});

onUnmounted(() => {
  cleanupChart?.();
  chart?.dispose();
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  unsubConnected?.();
  unsubData?.();
});

// 监听选中节点变化
watch(selectedNodeId, (newId, oldId) => {
  if (oldId) {
    eegWebSocket.unsubscribe([oldId]);
  }
  if (newId && isGraphFrozen.value) {
    subscribeToNode(newId);
  }
  // 切换节点时清空数据
  scanPosition = 0;
  isWrapped = false;
  totalReceivedSamples = 0;
  samples.forEach(s => s.fill(0));
  packetCount.value = 0;
});

// 监听时间窗口变化
watch(timeWindowSec, () => {
  // 窗口大小改变时重置扫描
  scanPosition = 0;
  isWrapped = false;
  requestRenderFrame();
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

/* 扫描模式信息 */
.scan-mode-info {
  margin-top: 8px;
}
</style>
