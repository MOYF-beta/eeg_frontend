<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        频谱可视化
        <v-tooltip location="bottom">
          <template #activator="{ props }">
            <v-icon v-bind="props" size="small" class="ml-2" color="info">
              mdi-information
            </v-icon>
          </template>
          <div>
            <div>数据源：{{ dataSourceText }}</div>
            <div v-if="targetNode">绑定节点: {{ targetNode.name }}</div>
            <div>FFT点数: {{ bufferSize }}</div>
          </div>
        </v-tooltip>
      </div>

      <div class="d-flex align-center ga-2">
        <!-- 数据源选择 -->
        <v-select
          v-model="selectedNodeId"
          :items="availableSpectrumNodes"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="选择数据源"
          style="width: 180px"
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

        <!-- 显示模式选择 -->
        <v-select
          v-model="displayMode"
          :items="displayModeItems"
          item-title="title"
          item-value="value"
          density="compact"
          variant="outlined"
          hide-details
          style="width: 120px"
          class="mr-2"
          :disabled="!canDisplay"
        />

        <!-- 通道选择 (仅在分通道模式下显示) -->
        <v-select
          v-if="displayMode === 'channels'"
          v-model="selectedChannels"
          :items="channelItems"
          density="compact"
          variant="outlined"
          hide-details
          multiple
          chips
          style="width: 150px"
          class="mr-2"
          :disabled="!canDisplay"
        />

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
        请从上方下拉菜单选择计算图中的频谱节点作为数据源。
        <router-link to="/cpgraph" target="_blank">前往计算图编辑器 →</router-link>
      </v-alert>

      <!-- 计算图未冻结提示 -->
      <v-alert v-else-if="!isGraphFrozen" type="warning" class="mb-4">
        计算图未冻结。请在<router-link to="/cpgraph" target="_blank">计算图编辑器</router-link>中点击"冻结"按钮启动数据流。
      </v-alert>

      <div class="spec-wrap">
        <canvas ref="canvasRef" class="spec-canvas" :class="{ 'disabled': !canDisplay }"></canvas>

        <!-- 无数据遮罩 -->
        <div v-if="!canDisplay" class="no-data-overlay">
          <v-icon size="48" color="grey-lighten-1">mdi-chart-bar</v-icon>
          <div class="text-h6 mt-2">{{ noDataText }}</div>
        </div>

        <div class="spec-footer">
          <div>采样率：{{ sampleRate }} Hz</div>
          <div>窗口：{{ bufferSize }} 点</div>
          <div>频率范围：0 - {{ sampleRate / 2 }} Hz</div>
          <div v-if="displayMode === 'average'">显示模式：通道平均</div>
          <div v-else>显示模式：{{ selectedChannels.length }} 个通道</div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
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
const sampleRate = 1000;
const bufferSize = 256;
const channelCount = 8;

// 状态
const canvasRef = ref<HTMLCanvasElement | null>(null);
const resizeObserver = ref<ResizeObserver | null>(null);
let animationId = 0;
let lastComputeTime = 0;

// 显示模式
const displayMode = ref<'average' | 'channels'>('average');
const displayModeItems = [
  { title: '通道平均', value: 'average' },
  { title: '分通道', value: 'channels' },
];

// 通道选择
const selectedChannels = ref<number[]>([0, 1, 2, 3]);
const channelItems = Array.from({ length: channelCount }, (_, i) => ({
  title: `CH${i + 1}`,
  value: i,
}));

// 数据源
const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);
const lastPacketTime = ref<number>(0);

// WebSocket 状态
const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

// 频谱数据
const spectrumData = ref<number[][]>(Array.from({ length: channelCount }, () => []));
const averageSpectrum = ref<number[]>([]);

// 原始样本数据
const samples: number[][] = Array.from({ length: channelCount }, () => []);

// 计算属性
const availableSpectrumNodes = computed(() => {
  // 包含SPECTRUM节点和OSC节点都可以作为频谱数据源
  return graphNodes.value.filter(n => n.type === 'SPECTRUM' || n.type === 'OSC');
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

// 方法
const isNodeBound = (nodeId: string) => {
  // 检查节点是否被其他示波器绑定
  return false; // TODO: 实现多示波器绑定检查
};

const onNodeSelected = (nodeId: string | null) => {
  if (nodeId) {
    sessionStore.bindOscilloscope('spectrum-' + Date.now(), nodeId);
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

// FFT计算
const computeFFT = (data: number[]): number[] => {
  const n = bufferSize;
  const mags = new Array(n / 2).fill(0);

  for (let k = 0; k < n / 2; k++) {
    let re = 0;
    let im = 0;
    for (let i = 0; i < n; i++) {
      // Hanning窗
      const w = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (n - 1)));
      const angle = (2 * Math.PI * k * i) / n;
      const xi = data[i] * w;
      re += xi * Math.cos(angle);
      im -= xi * Math.sin(angle);
    }
    mags[k] = Math.sqrt(re * re + im * im) / n;
  }

  return mags;
};

const computeSpectrum = () => {
  // 为每个通道计算频谱
  for (let ch = 0; ch < channelCount; ch++) {
    if (samples[ch].length >= bufferSize) {
      const data = samples[ch].slice(-bufferSize);
      spectrumData.value[ch] = computeFFT(data);
    }
  }

  // 计算平均频谱
  if (displayMode.value === 'average') {
    const avg = new Array(bufferSize / 2).fill(0);
    let count = 0;
    for (let ch = 0; ch < channelCount; ch++) {
      if (spectrumData.value[ch].length > 0) {
        for (let i = 0; i < bufferSize / 2; i++) {
          avg[i] += spectrumData.value[ch][i];
        }
        count++;
      }
    }
    if (count > 0) {
      for (let i = 0; i < bufferSize / 2; i++) {
        avg[i] /= count;
      }
    }
    averageSpectrum.value = avg;
  }
};

// 绘制
const resizeCanvas = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 260;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
};

const drawSpectrum = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 260;
  const leftPad = 48;
  const rightPad = 12;
  const topPad = 10;
  const bottomPad = 24;
  const plotWidth = width - leftPad - rightPad;
  const plotHeight = height - topPad - bottomPad;

  // 清空画布
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  // 绘制网格
  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = topPad + (i / 4) * plotHeight;
    ctx.beginPath();
    ctx.moveTo(leftPad, y);
    ctx.lineTo(leftPad + plotWidth, y);
    ctx.stroke();
  }
  for (let i = 0; i <= 4; i++) {
    const x = leftPad + (i / 4) * plotWidth;
    ctx.beginPath();
    ctx.moveTo(x, topPad);
    ctx.lineTo(x, topPad + plotHeight);
    ctx.stroke();
  }

  // 绘制频谱
  if (displayMode.value === 'average') {
    // 绘制平均频谱
    drawSingleSpectrum(ctx, averageSpectrum.value, '#7e57c2', leftPad, topPad, plotWidth, plotHeight);
  } else {
    // 绘制选中通道的频谱
    const colors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];
    selectedChannels.value.forEach((ch, idx) => {
      if (spectrumData.value[ch]?.length > 0) {
        drawSingleSpectrum(ctx, spectrumData.value[ch], colors[ch % colors.length], leftPad, topPad, plotWidth, plotHeight, ch);
      }
    });
  }

  // 绘制坐标轴标签
  ctx.fillStyle = '#546e7a';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i <= 4; i++) {
    const x = leftPad + (i / 4) * plotWidth;
    const hz = ((sampleRate / 2) * (i / 4)).toFixed(0);
    ctx.fillText(hz, x, height - 6);
  }
  ctx.textAlign = 'left';
  ctx.fillText('Hz', leftPad + plotWidth + 4, height - 6);

  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i++) {
    const y = topPad + (i / 4) * plotHeight;
    const value = (1 - i / 4).toFixed(1);
    ctx.fillText(value, leftPad - 6, y + 4);
  }
  ctx.save();
  ctx.translate(12, topPad + plotHeight / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.textAlign = 'center';
  ctx.fillText('幅值', 0, 0);
  ctx.restore();

  // 绘制图例（分通道模式）
  if (displayMode.value === 'channels') {
    const legendX = leftPad + 10;
    let legendY = topPad + 10;
    const colors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];
    selectedChannels.value.forEach(ch => {
      ctx.fillStyle = colors[ch % colors.length];
      ctx.fillRect(legendX, legendY, 12, 12);
      ctx.fillStyle = '#333';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(`CH${ch + 1}`, legendX + 16, legendY + 10);
      legendY += 16;
    });
  }
};

const drawSingleSpectrum = (
  ctx: CanvasRenderingContext2D,
  mags: number[],
  color: string,
  leftPad: number,
  topPad: number,
  plotWidth: number,
  plotHeight: number,
  channel?: number
) => {
  if (!mags || mags.length === 0) return;

  const maxMag = Math.max(...mags, 0.001);
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  mags.forEach((m, idx) => {
    const x = leftPad + (idx / (mags.length - 1)) * plotWidth;
    const y = topPad + plotHeight - (m / maxMag) * (plotHeight - 4);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
};

// WebSocket 数据处理器
const handleDataPacket = (packet: EegDataPacket) => {
  if (packet.nodeId !== selectedNodeId.value) return;

  packetCount.value++;
  lastPacketTime.value = Date.now();

  // 保存样本数据
  for (let ch = 0; ch < channelCount && ch < packet.channels.length; ch++) {
    samples[ch].push(packet.channels[ch]);
    if (samples[ch].length > bufferSize * 4) {
      samples[ch].shift();
    }
  }

  // 每200ms计算一次频谱
  const now = performance.now();
  if (now - lastComputeTime > 200) {
    lastComputeTime = now;
    computeSpectrum();
  }
};

// 更新计算图状态
const updateGraphState = async () => {
  try {
    const graph = await fetchGraph();
    graphNodes.value = graph.nodes || [];
    isGraphFrozen.value = graph.frozen || false;

    // 如果已冻结且有选中节点，订阅数据
    if (isGraphFrozen.value && selectedNodeId.value) {
      subscribeToNode(selectedNodeId.value);
    }
  } catch (e) {
    console.error('Failed to fetch graph:', e);
  }
};

// 动画循环
const loop = () => {
  drawSpectrum();
  animationId = requestAnimationFrame(loop);
};

// 清理函数和unsub函数需要在onUnmounted中访问
let unsubConnected: (() => void) | null = null;
let unsubDisconnected: (() => void) | null = null;
let unsubData: (() => void) | null = null;

// 生命周期
onMounted(async () => {
  try {
    // 加载计算图状态（先获取冻结状态）
    await updateGraphState();

    // 注册WebSocket回调（使用正确的方法调用）
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

    // 设置画布
    resizeObserver.value = new ResizeObserver(() => resizeCanvas());
    if (canvasRef.value) {
      resizeObserver.value.observe(canvasRef.value);
      resizeCanvas();
    }

    // 启动动画
    animationId = requestAnimationFrame(loop);

    // 如果WebSocket已连接，更新状态
    if (eegWebSocket.isConnected()) {
      wsStatus.value = 'connected';
      // 如果已连接，立即订阅当前选中的节点
      if (selectedNodeId.value && isGraphFrozen.value) {
        subscribeToNode(selectedNodeId.value);
      }
    } else if (isGraphFrozen.value) {
      // 如果计算图已冻结但WebSocket未连接，尝试连接
      eegWebSocket.connect();
    }
  } catch (err) {
    console.error('[SpectrumViewer] Error in onMounted:', err);
  }
});

onUnmounted(() => {
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  if (resizeObserver.value && canvasRef.value) {
    resizeObserver.value.unobserve(canvasRef.value);
  }
  cancelAnimationFrame(animationId);
  // 取消WebSocket回调注册
  unsubConnected?.();
  unsubDisconnected?.();
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
});
</script>

<style scoped>
.spec-wrap {
  position: relative;
}
.spec-canvas {
  width: 100%;
  height: 280px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  display: block;
}
.spec-canvas.disabled {
  opacity: 0.5;
}
.spec-footer {
  display: flex;
  gap: 16px;
  color: #666;
  font-size: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}
.no-data-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}
</style>
