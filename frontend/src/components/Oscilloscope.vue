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
              <div>最后: {{ lastPacketTimeStr }}</div>
            </div>
          </div>
        </div>

        <div class="osc-body">
          <div class="osc-labels">
            <div v-for="idx in channelCount" :key="idx" class="osc-label">
              CH{{ idx }}
            </div>
          </div>

          <div class="osc-canvas-wrap">
            <canvas ref="canvasRef" class="osc-canvas"></canvas>
            <!-- 无数据遮罩 -->
            <div v-if="!canDisplay" class="no-data-overlay">
              <v-icon size="48" color="grey-lighten-1">mdi-waveform</v-icon>
              <div class="text-h6 mt-2">{{ noDataText }}</div>
            </div>
          </div>

          <div class="osc-scales">
            <div v-for="(scale, idx) in channelScales" :key="idx" class="osc-scale">
              <div class="scale-label">Y</div>
              <v-slider
                v-model="channelScales[idx]"
                :min="0.2"
                :max="5"
                :step="0.1"
                density="compact"
                hide-details
                :disabled="!canDisplay"
              />
            </div>
          </div>
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

// 配置
const channelCount = 8;
const rowHeight = 90;

// 状态
const canvasRef = ref<HTMLCanvasElement | null>(null);
const mode = ref<'scan' | 'scroll'>('scroll');
const timeWindowSec = ref(5);
const channelScales = ref<number[]>(Array.from({ length: channelCount }, () => 1));

// 性能优化：使用固定大小的环形缓冲区，只保留窗口大小的数据
// 假设采样率1000Hz，窗口5秒，最多5000个点
const MAX_SAMPLES = 10000; // 最大缓存点数（10秒@1000Hz）
const samples: Array<Array<{ t: number; v: number }>> = Array.from(
  { length: channelCount },
  () => [],
);
let sampleStartIndex = 0; // 环形缓冲区起始索引

// 数据源
const selectedNodeId = ref<string | null>(null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);
const lastPacketTime = ref<number>(0);

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
  return selectedNodeId.value && isGraphFrozen.value;
});

const statusText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  if (!isGraphFrozen.value) return '未冻结';
  if (wsStatus.value === 'connected') return '接收中';
  if (wsStatus.value === 'connecting') return '连接中';
  if (wsStatus.value === 'error') return '错误';
  return '离线';
});

const statusColor = computed(() => {
  if (!selectedNodeId.value) return 'grey';
  if (!isGraphFrozen.value) return 'warning';
  if (wsStatus.value === 'connected') return 'success';
  if (wsStatus.value === 'connecting') return 'info';
  if (wsStatus.value === 'error') return 'error';
  return 'grey';
});

const statusIcon = computed(() => {
  if (!selectedNodeId.value) return 'mdi-help-circle';
  if (!isGraphFrozen.value) return 'mdi-pause-circle';
  if (wsStatus.value === 'connected') return 'mdi-check-circle';
  if (wsStatus.value === 'connecting') return 'mdi-loading';
  if (wsStatus.value === 'error') return 'mdi-alert-circle';
  return 'mdi-checkbox-blank-circle-outline';
});

const dataSourceText = computed(() => {
  if (!selectedNodeId.value) return '未选择数据源';
  const node = graphNodes.value.find(n => n.id === selectedNodeId.value);
  return node ? node.name : selectedNodeId.value;
});

const noDataText = computed(() => {
  if (!selectedNodeId.value) return '请选择数据源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  return '等待数据...';
});

const lastPacketTimeStr = computed(() => {
  if (!lastPacketTime.value) return '-';
  const diff = (Date.now() / 1000 - lastPacketTime.value).toFixed(1);
  return `${diff}s 前`;
});

// 检查节点是否已被其他示波器绑定
function isNodeBound(nodeId: string): boolean {
  const mappings = sessionStore.getOutputMappings();
  // 检查是否有其他示波器绑定了这个节点
  // 注意：当前示波器组件只是一个视图，实际的示波器实例在 sessionStore 中管理
  // 这里简化处理，只检查是否有绑定
  return Object.keys(mappings).includes(nodeId);
}

// 节点选择处理
function onNodeSelected(nodeId: string | null) {
  if (!nodeId) {
    selectedNodeId.value = null;
    return;
  }

  selectedNodeId.value = nodeId;

  // 确保示波器实例存在
  const oscId = 'osc-default'; // 默认示波器ID
  let osc = sessionStore.getOscilloscopeById(oscId);
  if (!osc) {
    // 如果不存在，创建一个默认示波器实例
    sessionStore.addOscilloscope({
      id: oscId,
      name: '默认示波器',
      isActive: true,
      timeWindow: 5,
      yScale: 1,
    });
  }

  // 更新 SessionStorage 的映射
  sessionStore.bindOutputNode(nodeId, oscId);

  // 更新 WebSocket 订阅，通知后端我们需要这个节点的数据
  eegWebSocket.updateSubscription();

  // 清空历史数据
  samples.forEach(ch => ch.length = 0);
  packetCount.value = 0;
}

// 解除绑定
function unbindNode() {
  if (!selectedNodeId.value) return;

  // 从 SessionStorage 解除绑定
  sessionStore.unbindOutputNode(selectedNodeId.value);

  // 更新 WebSocket 订阅
  eegWebSocket.updateSubscription();

  // 清空选择
  selectedNodeId.value = null;

  // 清空历史数据
  samples.forEach(ch => ch.length = 0);
  sampleStartIndex = 0;
  packetCount.value = 0;
  lastPacketTime.value = null;
}

// 加载计算图节点
async function loadGraphNodes() {
  try {
    const payload = await fetchGraph();
    graphNodes.value = payload.nodes;
    isGraphFrozen.value = payload.frozen;
    sessionStore.setGraph(payload);
  } catch (err) {
    console.error('Failed to load graph:', err);
    const stored = sessionStore.getGraph();
    graphNodes.value = stored.nodes;
    isGraphFrozen.value = stored.frozen;
  }
}

// WebSocket 数据处理 - 优化版本
function handleDataPacket(packet: EegDataPacket) {
  // 只处理选中的节点数据
  if (packet.nodeId !== selectedNodeId.value) return;

  const t = packet.timestamp / 1000;
  lastPacketTime.value = t;
  packetCount.value++;

  // 添加新数据点
  packet.channels.slice(0, channelCount).forEach((v, idx) => {
    samples[idx].push({ t, v });
  });

  // 只保留窗口大小的数据，丢弃旧数据
  pruneSamples(t);
}

function pruneSamples(now: number) {
  const cutoff = now - timeWindowSec.value;
  
  // 只检查第一个通道，假设所有通道数据同步
  const ch = samples[0];
  if (ch.length === 0) return;

  // 找到第一个在窗口内的数据点索引
  let startIdx = 0;
  while (startIdx < ch.length && ch[startIdx].t < cutoff) {
    startIdx++;
  }

  // 如果有过期的数据，一次性批量删除（比逐个shift高效）
  if (startIdx > 0) {
    for (let i = 0; i < channelCount; i++) {
      samples[i].splice(0, startIdx);
    }
  }

  // 如果数据量超过最大值，保留最新的MAX_SAMPLES个点
  if (ch.length > MAX_SAMPLES) {
    const excess = ch.length - MAX_SAMPLES;
    for (let i = 0; i < channelCount; i++) {
      samples[i].splice(0, excess);
    }
  }
}

// 绘图
let animationId = 0;
let sweepStart = 0;

function resizeCanvas() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 600;
  const height = rowHeight * channelCount;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function drawWaveform() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const width = canvas.clientWidth || 600;
  const height = rowHeight * channelCount;
  const leftPad = 46;
  const rightPad = 10;
  const plotWidth = width - leftPad - rightPad;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  // 绘制网格线
  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= channelCount; i += 1) {
    const y = i * rowHeight;
    ctx.beginPath();
    ctx.moveTo(leftPad, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }

  const now = lastPacketTime.value || Date.now() / 1000;
  const timeWindow = timeWindowSec.value;
  const baseScale = rowHeight / 2 - 8;

  samples.forEach((ch, idx) => {
    if (ch.length < 2) return;
    const rowTop = idx * rowHeight;
    const midY = rowTop + rowHeight / 2;
    const scale = channelScales.value[idx] || 1;

    // 垂直网格线
    ctx.strokeStyle = '#cfd8dc';
    ctx.lineWidth = 1;
    const tickCount = 4;
    for (let tIdx = 0; tIdx <= tickCount; tIdx += 1) {
      const x = leftPad + (tIdx / tickCount) * plotWidth;
      ctx.beginPath();
      ctx.moveTo(x, rowTop + 8);
      ctx.lineTo(x, rowTop + rowHeight - 8);
      ctx.stroke();
    }

    // 绘制波形
    ctx.strokeStyle = '#1976d2';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    let prevX = -1;
    ch.forEach((p) => {
      let x = 0;
      if (mode.value === 'scroll') {
        x = leftPad + ((p.t - (now - timeWindow)) / timeWindow) * plotWidth;
        if (x < leftPad || x > leftPad + plotWidth) return;
      } else {
        const offset = (p.t - sweepStart) % timeWindow;
        x = leftPad + (offset / timeWindow) * plotWidth;
      }
      const y = midY - p.v * baseScale * scale;
      if (prevX >= 0 && x < prevX) {
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x, y);
      } else if (prevX < 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
      prevX = x;
    });
    ctx.stroke();

    // 中线
    ctx.strokeStyle = '#bdbdbd';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(leftPad, midY);
    ctx.lineTo(width, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    // 缩放标签
    ctx.fillStyle = '#607d8b';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(`${(1 / scale).toFixed(1)}x`, leftPad - 6, rowTop + 14);
  });

  // 时间轴标签
  ctx.fillStyle = '#546e7a';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  const tickCount = 4;
  for (let tIdx = 0; tIdx <= tickCount; tIdx += 1) {
    const x = leftPad + (tIdx / tickCount) * plotWidth;
    const label = (timeWindow * (tIdx / tickCount)).toFixed(1);
    ctx.fillText(label, x, height - 6);
  }
  ctx.textAlign = 'left';
  ctx.fillText('s', leftPad + plotWidth + 4, height - 6);
}

function drawLoop() {
  drawWaveform();
  animationId = requestAnimationFrame(drawLoop);
}

// 生命周期
let wsUnsubscribe: (() => void) | null = null;
let wsStatusUnsubscribe: (() => void) | null = null;
let resizeObserver: ResizeObserver | null = null;

onMounted(async () => {
  await loadGraphNodes();

  // 如果有绑定的节点，自动选择
  const mappings = sessionStore.getOutputMappings();
  const oscId = 'osc-default';
  const boundNodeId = Object.entries(mappings).find(([_, id]) => id === oscId)?.[0];
  if (boundNodeId) {
    selectedNodeId.value = boundNodeId;
  }

  // 订阅 WebSocket 数据
  wsUnsubscribe = eegWebSocket.onData(handleDataPacket);

  // 订阅 WebSocket 状态
  wsStatusUnsubscribe = eegWebSocket.onStatusChange((status) => {
    wsStatus.value = status;
  });

  // 监听 sessionStore 变化
  sessionStore.subscribe((state) => {
    if (state.graph.nodes.length > 0) {
      graphNodes.value = state.graph.nodes;
    }
    isGraphFrozen.value = state.graph.frozen;
  });

  // 初始化画布
  resizeObserver = new ResizeObserver(() => resizeCanvas());
  if (canvasRef.value) {
    resizeObserver.observe(canvasRef.value);
    resizeCanvas();
  }

  // 启动动画循环
  animationId = requestAnimationFrame(drawLoop);

  // 确保 WebSocket 已连接
  if (!eegWebSocket.isConnected()) {
    eegWebSocket.connect();
  }
});

onUnmounted(() => {
  if (wsUnsubscribe) wsUnsubscribe();
  if (wsStatusUnsubscribe) wsStatusUnsubscribe();
  if (resizeObserver && canvasRef.value) resizeObserver.unobserve(canvasRef.value);
  if (animationId) cancelAnimationFrame(animationId);
});

// 监听时间窗口变化
watch([timeWindowSec, mode], () => {
  if (lastPacketTime.value) sweepStart = lastPacketTime.value;
  pruneSamples(lastPacketTime.value || Date.now() / 1000);
});
</script>

<style scoped>
.osc-root {
  display: grid;
  gap: 16px;
}
.osc-controls {
  display: grid;
  grid-template-columns: 180px 1fr 120px;
  gap: 16px;
  align-items: center;
}
.control-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}
.osc-body {
  display: grid;
  grid-template-columns: 60px 1fr 160px;
  gap: 12px;
  align-items: stretch;
}
.osc-labels {
  display: grid;
  grid-template-rows: repeat(8, 90px);
  align-items: center;
  font-weight: 600;
  color: #546e7a;
}
.osc-label {
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
}
.osc-canvas-wrap {
  position: relative;
  width: 100%;
  height: 720px;
}
.osc-canvas {
  width: 100%;
  height: 100%;
  display: block;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
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
  color: #666;
}
.osc-scales {
  display: grid;
  grid-template-rows: repeat(8, 90px);
  gap: 0;
}
.osc-scale {
  display: grid;
  grid-template-columns: 20px 1fr;
  align-items: center;
}
.scale-label {
  font-size: 12px;
  color: #666;
}
</style>