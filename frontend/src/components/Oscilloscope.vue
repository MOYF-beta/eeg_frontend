<template>
  <v-card class="mb-4" variant="tonal">

    <v-card-text>
      <!-- 未选择数据源提示 -->
      <v-alert
        v-if="!selectedNodeId"
        type="info"
        variant="tonal"
        class="mb-4 osc-select-source-alert"
        elevation="0"
        border="start"
        @click="sourceDialogOpen = true"
      >
        <div>
          请从上方下拉菜单选择计算图中的示波器节点作为数据源。
          <span class="osc-select-source-link">请选择数据源</span>
        </div>
        <router-link to="/cpgraph" target="_blank" @click.stop>
          前往计算图编辑器 →
        </router-link>
      </v-alert>

      <!-- 计算图未冻结提示 -->
      <v-alert v-else-if="!isGraphFrozen" type="warning" class="mb-4">
        计算图未冻结。请在<router-link to="/cpgraph" target="_blank">计算图编辑器</router-link>中点击"冻结"按钮启动数据流。
      </v-alert>

      <div class="osc-root">
        <div class="osc-statusbar">
          <div class="osc-status-section osc-time-section">
            <div class="osc-status-label">时间窗口</div>
            <div class="osc-status-inline osc-time-inline">
              <span
                class="osc-time-btn"
                :class="{ disabled: !canDisplay }"
                @click="canDisplay && stepTimeWindow(-1)"
              >-</span>
              <span class="osc-time-value">{{ timeWindowSec }}s</span>
              <span
                class="osc-time-btn"
                :class="{ disabled: !canDisplay }"
                @click="canDisplay && stepTimeWindow(1)"
              >+</span>
            </div>
          </div>
          <div class="osc-status-section osc-toggle-section">
            <v-btn
              size="x-small"
              variant="tonal"
              class="osc-toggle-button"
              :class="{ 'osc-toggle-active': centerEnabled }"
              :color="centerEnabled ? 'primary' : 'grey'"
              :disabled="!canDisplay"
              @click="centerEnabled = !centerEnabled"
            >
              居中
            </v-btn>
          </div>
          <div class="osc-status-section osc-toggle-section">
            <v-btn
              size="x-small"
              variant="tonal"
              class="osc-toggle-button"
              :class="{ 'osc-toggle-active': autoGainEnabled }"
              :color="autoGainEnabled ? 'primary' : 'grey'"
              :disabled="!canDisplay"
              @click="autoGainEnabled = !autoGainEnabled"
            >
              自动增益
            </v-btn>
          </div>
          <div class="osc-status-section osc-status-source">
            <v-btn
              size="x-small"
              variant="outlined"
              :disabled="availableOscNodes.length === 0"
              @click="sourceDialogOpen = true"
            >
              {{ signalSourceButtonText }}
            </v-btn>
            <v-chip size="x-small" :color="statusColor">
              <v-icon left size="x-small">{{ statusIcon }}</v-icon>
              {{ statusText }}
            </v-chip>
          </div>
          <div class="osc-status-section">
            <div class="osc-status-label">接收状态</div>
            <div class="osc-status-text">接收: {{ packetCount }} 包</div>
            <div class="osc-status-text">扫描: {{ scanPositionDisplay }} / {{ timeWindowSec * 1000 }}</div>
          </div>
          <div class="osc-status-section">
            <div class="osc-status-label">采样率</div>
            <div class="osc-status-text">{{ SAMPLE_RATE }}Hz</div>
          </div>
          <div class="osc-status-section osc-status-close">
            <v-btn
              size="x-small"
              variant="text"
              color="grey"
              icon="mdi-close"
              @click="$emit('remove')"
            />
          </div>
        </div>

        <v-dialog v-model="sourceDialogOpen" max-width="420">
          <v-card>
            <v-card-title>信号源设置</v-card-title>
            <v-card-text class="pt-2">
              <v-list density="compact">
                <v-list-item
                  v-for="node in availableOscNodes"
                  :key="node.id"
                  @click="onNodeSelected(node.id)"
                >
                  <template #title>{{ node.name }}</template>
                  <template #append>
                    <v-chip v-if="selectedNodeId === node.id" size="x-small" color="primary">
                      已选择
                    </v-chip>
                  </template>
                </v-list-item>
              </v-list>
            </v-card-text>
            <v-card-actions class="justify-space-between">
              <v-btn
                size="small"
                color="error"
                variant="text"
                :disabled="!selectedNodeId"
                @click="unbindNode"
              >
                解除绑定
              </v-btn>
              <v-btn size="small" variant="text" @click="sourceDialogOpen = false">关闭</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <div ref="chartContainerRef" class="osc-chart-container">
          <!-- Canvas 分层渲染：网格 / 波形 / 扫描线 -->
          <div class="osc-chart">
            <canvas ref="gridCanvasRef" class="osc-canvas" aria-hidden="true"></canvas>
            <canvas ref="waveCanvasRef" class="osc-canvas" aria-hidden="true"></canvas>
            <canvas ref="overlayCanvasRef" class="osc-canvas osc-overlay" aria-hidden="true"></canvas>
          </div>

          <!-- 无数据遮罩 -->
          <div v-if="!canDisplay" class="no-data-overlay">
            <v-icon size="48" color="grey-lighten-1">mdi-waveform</v-icon>
            <div class="text-h6 mt-2">{{ noDataText }}</div>
          </div>

          <div class="osc-left-axis">
            <div
              v-for="ch in channelCount"
              :key="`axis-${ch}`"
              class="osc-left-axis-row"
              :style="[getChannelRowStyle(ch - 1), { '--channel-line-color': getChannelLineColor(ch - 1) }]"
            >
              <div class="osc-left-axis-label">CH{{ ch }}</div>
              <div class="osc-left-axis-values">
                <div>+{{ getChannelTick(ch - 1).max }}</div>
                <div>{{ getChannelTick(ch - 1).min }}</div>
              </div>
            </div>
          </div>

          <div class="osc-sidebar" :class="{ collapsed: sidebarCollapsed }">
            <button
              class="osc-sidebar-toggle"
              type="button"
              @click="sidebarCollapsed = !sidebarCollapsed"
            >
              <v-icon size="12">{{ sidebarCollapsed ? 'mdi-chevron-left' : 'mdi-chevron-right' }}</v-icon>
            </button>
            <div
              v-for="ch in channelCount"
              :key="`ch-${ch}`"
              class="osc-sidebar-row"
              :style="getChannelRowStyle(ch - 1)"
              v-show="!sidebarCollapsed"
            >
              <div class="osc-gain-row osc-gain-row-horizontal">
                <span class="osc-gain-total" :class="{ 'is-auto': autoGainEnabled }">{{ formatGainDisplay(ch - 1) }}</span>
                <span class="osc-gain-equals">=</span>
                <span class="osc-gain-label">*1eN</span>
                <div class="osc-gain-mini-ctrl">
                  <span
                    class="osc-gain-btn"
                    :class="{ disabled: !canDisplay || autoGainEnabled }"
                    @click="!autoGainEnabled && stepGainExp(ch - 1, -1)"
                  >-</span>
                  <span class="osc-gain-value" :class="{ 'is-auto': autoGainEnabled }">{{ gainExpByCh[ch - 1] }}</span>
                  <span
                    class="osc-gain-btn"
                    :class="{ disabled: !canDisplay || autoGainEnabled }"
                    @click="!autoGainEnabled && stepGainExp(ch - 1, 1)"
                  >+</span>
                </div>

                <span class="osc-gain-label">*1</span>
                <div class="osc-gain-mini-ctrl">
                  <span
                    class="osc-gain-btn"
                    :class="{ disabled: !canDisplay || autoGainEnabled }"
                    @click="!autoGainEnabled && stepGainFine(ch - 1, -1)"
                  >-</span>
                  <span class="osc-gain-value" :class="{ 'is-auto': autoGainEnabled }">{{ gainFineByCh[ch - 1].toFixed(1) }}</span>
                  <span
                    class="osc-gain-btn"
                    :class="{ disabled: !canDisplay || autoGainEnabled }"
                    @click="!autoGainEnabled && stepGainFine(ch - 1, 1)"
                  >+</span>
                </div>
              </div>
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
const MIN_WINDOW_SEC = 1;
const LEFT_AXIS_WIDTH = 70;
const SIDEBAR_WIDTH = 220;
const SIDEBAR_COLLAPSED_WIDTH = 24;
const AMPLITUDE_REF_UV = 100;
const GAIN_FINE_MIN = 0.1;
const GAIN_FINE_MAX = 9.9;
const GAIN_EXP_MIN = -3;
const GAIN_EXP_MAX = 3;

// 性能优化：目标刷新率 30fps
const TARGET_FPS = 30;
const FRAME_INTERVAL = 1000 / TARGET_FPS;

let lastFrameTime = 0;
let isFramePending = false;

// 状态
const chartContainerRef = ref<HTMLDivElement | null>(null);
const gridCanvasRef = ref<HTMLCanvasElement | null>(null);
const waveCanvasRef = ref<HTMLCanvasElement | null>(null);
const overlayCanvasRef = ref<HTMLCanvasElement | null>(null);
let gridCtx: CanvasRenderingContext2D | null = null;
let waveCtx: CanvasRenderingContext2D | null = null;
let overlayCtx: CanvasRenderingContext2D | null = null;
let resizeObserver: ResizeObserver | null = null;

const canvasSize = ref({ width: 0, height: 0, dpr: 1 });
const plotMetrics = ref({
  left: LEFT_AXIS_WIDTH,
  right: 20 + SIDEBAR_WIDTH,
  top: 20,
  bottom: 28,
  width: 0,
  height: 0,
  channelSpacing: 0,
  amplitudeScale: 0,
});
const timeWindowSec = ref(DEFAULT_WINDOW_SEC);
const gainFineByCh = ref<number[]>(Array.from({ length: channelCount }, () => 1.0));
const gainExpByCh = ref<number[]>(Array.from({ length: channelCount }, () => 0));
const autoGainDisplay = ref<number[]>(Array.from({ length: channelCount }, () => 1));
const centerEnabled = ref(false);
const autoGainEnabled = ref(false);
let isAutoGainSync = false;
const channelAbsDisplay = ref<number[]>(Array.from({ length: channelCount }, () => 1));
const sidebarCollapsed = ref(false);
const sourceDialogOpen = ref(false);
const channelRanges = ref<Array<{ max: number; min: number }>>(Array.from({ length: channelCount }, () => ({ max: 0, min: 0 })));

// === 扫描模式数据存储 ===
// 动态大小的双缓冲区：当前窗口 + 上一个窗口
let samplesCurrent: number[][] = [];
let samplesPrev: number[][] = [];
const scanPosition = ref(0); // 扫描线位置（0 ~ windowSize-1）
const isWrapped = ref(false); // 是否已完成至少一次完整扫描
const totalReceivedSamples = ref(0);
let scanCycle = 0;
let lastRenderedCycle = 0;
let lastRenderedPosition = 0;

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
const totalSamples = computed(() => totalReceivedSamples.value);

// 扫描位置显示（响应式）
const scanPositionDisplay = computed(() => scanPosition.value);

const noDataText = computed(() => {
  if (!selectedNodeId.value) return '请选择数据源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  if (wsStatus.value !== 'connected') return '等待连接';
  return '等待数据';
});

const signalSourceButtonText = computed(() => {
  return selectedNodeId.value ? `信号源: ${dataSourceText.value}` : '信号源: 未选择';
});

const getChannelTick = (ch: number) => {
  const range = channelRanges.value[ch] || { max: 0, min: 0 };
  const format = (value: number) => Number(value.toFixed(1));
  return { max: format(range.max), min: format(range.min) };
};

const getChannelRowStyle = (ch: number) => {
  const top = plotMetrics.value.top + plotMetrics.value.channelSpacing * ch;
  const height = plotMetrics.value.channelSpacing;
  return {
    top: `${top}px`,
    height: `${height}px`,
  } as Record<string, string>;
};

const hexToRgba = (hex: string, alpha: number) => {
  const normalized = hex.replace('#', '');
  const padded = normalized.length === 3
    ? normalized.split('').map(char => char + char).join('')
    : normalized;
  const value = parseInt(padded.substring(0, 6), 16);
  const r = (value >> 16) & 0xff;
  const g = (value >> 8) & 0xff;
  const b = value & 0xff;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
};

const getChannelLineColor = (ch: number, alpha = 0.28) => {
  const index = Math.max(0, Math.min(ch, colors.length - 1));
  return hexToRgba(colors[index], alpha);
};

const formatGainDisplay = (ch: number) => {
  const gain = autoGainEnabled.value
    ? (autoGainDisplay.value[ch] ?? 1)
    : getEffectiveGain(ch);
  return gain.toFixed(2);
};

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
  resetAllData();
};

const createSamplesBuffer = (windowSize: number) => {
  const size = Math.max(1, windowSize);
  samplesCurrent = Array.from({ length: channelCount }, () => new Array(size).fill(0));
  samplesPrev = Array.from({ length: channelCount }, () => new Array(size).fill(0));
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const normalizeGainFine = (ch: number) => {
  const value = gainFineByCh.value[ch] ?? 0;
  const normalized = clamp(Number(value || 0), GAIN_FINE_MIN, GAIN_FINE_MAX);
  gainFineByCh.value[ch] = Number(normalized.toFixed(1));
};

const normalizeGainExp = (ch: number) => {
  const value = gainExpByCh.value[ch] ?? 0;
  gainExpByCh.value[ch] = clamp(Math.round(Number(value || 0)), GAIN_EXP_MIN, GAIN_EXP_MAX);
};

const normalizeTimeWindow = () => {
  timeWindowSec.value = clamp(Math.round(Number(timeWindowSec.value || DEFAULT_WINDOW_SEC)), MIN_WINDOW_SEC, MAX_WINDOW_SEC);
};

const stepGainFine = (ch: number, direction: number) => {
  const current = gainFineByCh.value[ch] ?? 0;
  const next = Number(current || 0) + direction * 0.1;
  gainFineByCh.value[ch] = clamp(Number(next.toFixed(1)), GAIN_FINE_MIN, GAIN_FINE_MAX);
};

const stepGainExp = (ch: number, direction: number) => {
  const current = gainExpByCh.value[ch] ?? 0;
  const next = Math.round(Number(current || 0)) + direction;
  gainExpByCh.value[ch] = clamp(next, GAIN_EXP_MIN, GAIN_EXP_MAX);
};

const getEffectiveGain = (ch: number) => {
  const fine = gainFineByCh.value[ch] ?? 1;
  const exp = gainExpByCh.value[ch] ?? 0;
  return fine * Math.pow(10, exp);
};

const stepTimeWindow = (direction: number) => {
  const next = Math.round(Number(timeWindowSec.value || DEFAULT_WINDOW_SEC)) + direction;
  timeWindowSec.value = clamp(next, MIN_WINDOW_SEC, MAX_WINDOW_SEC);
};

const subscribeToNode = (nodeId: string) => {
  if (isGraphFrozen.value) {
    eegWebSocket.subscribe([nodeId]);
  }
};

const updatePlotMetrics = () => {
  const { width, height } = canvasSize.value;
  const left = LEFT_AXIS_WIDTH;
  const sidebarWidth = sidebarCollapsed.value ? SIDEBAR_COLLAPSED_WIDTH : SIDEBAR_WIDTH;
  const right = 20 + sidebarWidth;
  const top = plotMetrics.value.top;
  const bottom = plotMetrics.value.bottom;
  const plotWidth = Math.max(0, width - left - right);
  const plotHeight = Math.max(0, height - top - bottom);
  const channelSpacing = channelCount > 0 ? plotHeight / (channelCount + 0.5) : 0;
  const amplitudeScale = AMPLITUDE_REF_UV > 0 ? (channelSpacing * 0.35) / AMPLITUDE_REF_UV : 0;

  plotMetrics.value = {
    left,
    right,
    top,
    bottom,
    width: plotWidth,
    height: plotHeight,
    channelSpacing,
    amplitudeScale,
  };
};

const resizeCanvas = (canvas: HTMLCanvasElement | null) => {
  if (!canvas) return;
  const { width, height, dpr } = canvasSize.value;
  canvas.width = Math.max(1, Math.floor(width * dpr));
  canvas.height = Math.max(1, Math.floor(height * dpr));
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
};

const initCanvas = () => {
  if (!chartContainerRef.value || !gridCanvasRef.value || !waveCanvasRef.value || !overlayCanvasRef.value) return;

  gridCtx = gridCanvasRef.value.getContext('2d');
  waveCtx = waveCanvasRef.value.getContext('2d');
  overlayCtx = overlayCanvasRef.value.getContext('2d');

  const handleResize = () => {
    if (!chartContainerRef.value) return;
    const rect = chartContainerRef.value.getBoundingClientRect();
    canvasSize.value = {
      width: Math.max(1, Math.floor(rect.width)),
      height: Math.max(1, Math.floor(rect.height)),
      dpr: Math.max(1, window.devicePixelRatio || 1),
    };
    resizeCanvas(gridCanvasRef.value);
    resizeCanvas(waveCanvasRef.value);
    resizeCanvas(overlayCanvasRef.value);
    updatePlotMetrics();
    drawGrid();
    clearWaveCanvas();
    clearOverlayCanvas();
  };

  resizeObserver = new ResizeObserver(handleResize);
  resizeObserver.observe(chartContainerRef.value);
  handleResize();
};

const clearWaveCanvas = () => {
  if (!waveCtx) return;
  const { width, height } = canvasSize.value;
  waveCtx.clearRect(0, 0, width, height);
};

const clearOverlayCanvas = () => {
  if (!overlayCtx) return;
  const { width, height } = canvasSize.value;
  overlayCtx.clearRect(0, 0, width, height);
};

const drawGrid = () => {
  if (!gridCtx) return;
  const { width, height } = canvasSize.value;
  const { left, top, width: plotWidth, height: plotHeight, channelSpacing } = plotMetrics.value;

  gridCtx.clearRect(0, 0, width, height);

  gridCtx.save();
  gridCtx.fillStyle = '#ffffff';
  gridCtx.fillRect(0, 0, width, height);

  gridCtx.strokeStyle = '#f0f0f0';
  gridCtx.lineWidth = 1;

  const verticalLines = 10;
  for (let i = 0; i <= verticalLines; i++) {
    const x = left + (plotWidth * i) / verticalLines;
    gridCtx.beginPath();
    gridCtx.moveTo(x, top);
    gridCtx.lineTo(x, top + plotHeight);
    gridCtx.stroke();
  }

  for (let ch = 0; ch < channelCount; ch++) {
    const y = top + channelSpacing * (ch + 0.5);
    gridCtx.strokeStyle = getChannelLineColor(ch, 0.35);
    gridCtx.lineWidth = 1;
    gridCtx.beginPath();
    gridCtx.moveTo(left, y);
    gridCtx.lineTo(left + plotWidth, y);
    gridCtx.stroke();
  }

  gridCtx.fillStyle = '#666';
  gridCtx.font = '12px sans-serif';
  gridCtx.textAlign = 'right';
  gridCtx.textBaseline = 'middle';
  for (let ch = 0; ch < channelCount; ch++) {
    const y = top + channelSpacing * (ch + 0.5);
    gridCtx.fillText(`CH${ch + 1}`, left - 8, y);
  }

  gridCtx.restore();

  // X 轴刻度（底部）
  gridCtx.save();
  gridCtx.fillStyle = '#777';
  gridCtx.font = '10px sans-serif';
  gridCtx.textAlign = 'center';
  gridCtx.textBaseline = 'top';
  const ticks = 5;
  for (let i = 0; i <= ticks; i++) {
    const x = left + (plotWidth * i) / ticks;
    const label = `${((timeWindowSec.value * i) / ticks).toFixed(1)}s`;
    gridCtx.fillText(label, x, top + plotHeight + 4);
  }
  gridCtx.restore();
};

const drawScanLine = () => {
  if (!overlayCtx) return;
  const { width, height } = canvasSize.value;
  const { left, top, width: plotWidth, height: plotHeight } = plotMetrics.value;
  const windowSize = Math.max(1, timeWindowSec.value * SAMPLE_RATE);
  const x = left + (plotWidth * scanPosition.value) / (windowSize - 1 || 1);

  overlayCtx.clearRect(0, 0, width, height);
  overlayCtx.save();
  overlayCtx.strokeStyle = '#ff5722';
  overlayCtx.lineWidth = 2;
  overlayCtx.beginPath();
  overlayCtx.moveTo(x, top);
  overlayCtx.lineTo(x, top + plotHeight);
  overlayCtx.stroke();
  overlayCtx.restore();
};

type ChannelStats = {
  means: number[];
  maxAbs: number[];
  rawMax: number[];
  rawMin: number[];
};

const computeChannelStats = (buffer: number[][], count: number): ChannelStats => {
  const means = new Array(channelCount).fill(0);
  const maxAbs = new Array(channelCount).fill(1);
  const rawMax = new Array(channelCount).fill(-Infinity);
  const rawMin = new Array(channelCount).fill(Infinity);

  if (count <= 0) {
    return {
      means,
      maxAbs,
      rawMax: rawMax.map(() => 0),
      rawMin: rawMin.map(() => 0),
    };
  }

  for (let ch = 0; ch < channelCount; ch++) {
    const channel = buffer[ch];
    if (!channel) continue;
    let sum = 0;
    for (let i = 0; i < count; i++) {
      sum += channel[i] || 0;
    }
    const mean = sum / count;
    means[ch] = mean;

    let peak = 0;
    for (let i = 0; i < count; i++) {
      const value = channel[i] || 0;
      rawMax[ch] = Math.max(rawMax[ch], value);
      rawMin[ch] = Math.min(rawMin[ch], value);
      const v = value - (centerEnabled.value ? mean : 0);
      const abs = Math.abs(v);
      if (abs > peak) peak = abs;
    }
    maxAbs[ch] = peak || 1;
  }

  return {
    means,
    maxAbs,
    rawMax: rawMax.map((value) => (Number.isFinite(value) ? value : 0)),
    rawMin: rawMin.map((value) => (Number.isFinite(value) ? value : 0)),
  };
};

const syncAutoGainDisplay = (stats: ChannelStats, channelSpacing: number) => {
  if (!autoGainEnabled.value || !centerEnabled.value) return;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;
  const amplitudeScale = plotMetrics.value.amplitudeScale || 1;

  isAutoGainSync = true;
  for (let ch = 0; ch < channelCount; ch++) {
    const peak = stats.maxAbs[ch] || 1;
    const scale = targetHalfHeight / Math.max(peak, 1e-6);
    const gainEquivalent = scale / amplitudeScale;
    autoGainDisplay.value[ch] = gainEquivalent;

    const exp = clamp(Math.floor(Math.log10(Math.max(gainEquivalent, 1e-6))), GAIN_EXP_MIN, GAIN_EXP_MAX);
    const fine = clamp(gainEquivalent / Math.pow(10, exp), GAIN_FINE_MIN, GAIN_FINE_MAX);
    gainExpByCh.value[ch] = exp;
    gainFineByCh.value[ch] = Number(fine.toFixed(1));
  }
  isAutoGainSync = false;
};

const updateChannelRange = (stats: ChannelStats) => {
  channelRanges.value = stats.rawMax.map((max, ch) => ({
    max,
    min: stats.rawMin[ch] ?? 0,
  }));
};

const drawSamples = (
  fromPos: number,
  toPosExclusive: number,
  buffer: number[][],
  stats: ChannelStats
) => {
  if (!waveCtx) return;
  const { left, top, width: plotWidth, channelSpacing, amplitudeScale } = plotMetrics.value;
  const windowSize = Math.max(1, timeWindowSec.value * SAMPLE_RATE);
  const baseX = (pos: number) => left + (plotWidth * pos) / (windowSize - 1 || 1);
  const useAuto = centerEnabled.value && autoGainEnabled.value;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;

  for (let ch = 0; ch < channelCount; ch++) {
    waveCtx.strokeStyle = colors[ch];
    waveCtx.lineWidth = 1;
    waveCtx.beginPath();
    let started = false;

    for (let pos = fromPos; pos < toPosExclusive; pos++) {
      const x = baseX(pos);
      const baseline = top + channelSpacing * (ch + 0.5);
      const value = buffer[ch]?.[pos] || 0;
      const mean = centerEnabled.value ? (stats.means[ch] || 0) : 0;
      const centered = value - mean;
      const peak = stats.maxAbs[ch] || 1;
      const manualGain = getEffectiveGain(ch) * amplitudeScale;
      const scaled = useAuto ? (centered / peak) * targetHalfHeight : centered * manualGain;
      const y = baseline - scaled;

      if (!started) {
        if (pos > 0) {
          const prevPos = pos - 1;
          const prevX = baseX(prevPos);
          const prevValue = buffer[ch]?.[prevPos] || 0;
          const prevMean = centerEnabled.value ? (stats.means[ch] || 0) : 0;
          const prevCentered = prevValue - prevMean;
          const prevPeak = stats.maxAbs[ch] || 1;
          const manualGainPrev = getEffectiveGain(ch) * amplitudeScale;
          const prevScaled = useAuto ? (prevCentered / prevPeak) * targetHalfHeight : prevCentered * manualGainPrev;
          const prevY = baseline - prevScaled;
          waveCtx.moveTo(prevX, prevY);
          waveCtx.lineTo(x, y);
        } else {
          waveCtx.moveTo(x, y);
        }
        started = true;
      } else {
        waveCtx.lineTo(x, y);
      }
    }

    if (started) {
      waveCtx.stroke();
    }
  }
};

const drawFullWindow = () => {
  if (!waveCtx) return;
  const windowSize = Math.max(1, timeWindowSec.value * SAMPLE_RATE);
  const currentCount = Math.min(windowSize, scanPosition.value);
  const prevCount = isWrapped.value ? windowSize : 0;
  const statsCurrent = computeChannelStats(samplesCurrent, currentCount);
  const statsPrev = computeChannelStats(samplesPrev, prevCount);

  clearWaveCanvas();

  const { left, top, width: plotWidth, channelSpacing, amplitudeScale } = plotMetrics.value;
  const baseX = (pos: number) => left + (plotWidth * pos) / (windowSize - 1 || 1);
  const useAuto = centerEnabled.value && autoGainEnabled.value;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;

  syncAutoGainDisplay(statsCurrent, channelSpacing);
  updateChannelRange(statsCurrent);
  channelAbsDisplay.value = statsCurrent.maxAbs.slice();

  for (let ch = 0; ch < channelCount; ch++) {
    waveCtx.strokeStyle = colors[ch];
    waveCtx.lineWidth = 1;
    waveCtx.beginPath();
    let started = false;

    for (let pos = 0; pos < windowSize; pos++) {
      const useCurrent = pos < scanPosition.value;
      const buffer = useCurrent ? samplesCurrent : samplesPrev;
      const stats = useCurrent ? statsCurrent : statsPrev;
      const value = buffer[ch]?.[pos] || 0;
      const mean = centerEnabled.value ? (stats.means[ch] || 0) : 0;
      const centered = value - mean;
      const baseline = top + channelSpacing * (ch + 0.5);
      const x = baseX(pos);
      const peak = stats.maxAbs[ch] || 1;
      const manualGain = getEffectiveGain(ch) * amplitudeScale;
      const scaled = useAuto ? (centered / peak) * targetHalfHeight : centered * manualGain;
      const y = baseline - scaled;

      if (!started) {
        if (pos > 0) {
          const prevPos = pos - 1;
          const prevUseCurrent = prevPos < scanPosition.value;
          const prevBuffer = prevUseCurrent ? samplesCurrent : samplesPrev;
          const prevStats = prevUseCurrent ? statsCurrent : statsPrev;
          const prevValue = prevBuffer[ch]?.[prevPos] || 0;
          const prevMean = centerEnabled.value ? (prevStats.means[ch] || 0) : 0;
          const prevCentered = prevValue - prevMean;
          const prevX = baseX(prevPos);
          const prevPeak = prevStats.maxAbs[ch] || 1;
          const manualGainPrev = getEffectiveGain(ch) * amplitudeScale;
          const prevScaled = useAuto ? (prevCentered / prevPeak) * targetHalfHeight : prevCentered * manualGainPrev;
          const prevY = baseline - prevScaled;
          waveCtx.moveTo(prevX, prevY);
          waveCtx.lineTo(x, y);
        } else {
          waveCtx.moveTo(x, y);
        }
        started = true;
      } else {
        waveCtx.lineTo(x, y);
      }
    }

    if (started) {
      waveCtx.stroke();
    }
  }
};

const redrawAllSamples = () => {
  if (!canDisplay.value) return;
  drawFullWindow();
  lastRenderedCycle = scanCycle;
  lastRenderedPosition = scanPosition.value;
  drawScanLine();
};

const renderFrame = () => {
  if (!canDisplay.value) return;
  const windowSize = Math.max(1, timeWindowSec.value * SAMPLE_RATE);
  const currentCount = Math.min(windowSize, scanPosition.value);
  const statsCurrent = computeChannelStats(samplesCurrent, currentCount);
  updateChannelRange(statsCurrent);

  if (lastRenderedCycle !== scanCycle) {
    lastRenderedCycle = scanCycle;
    lastRenderedPosition = 0;
    drawFullWindow();
  }

  const targetPosition = scanPosition.value;
  if (targetPosition > lastRenderedPosition) {
    syncAutoGainDisplay(statsCurrent, plotMetrics.value.channelSpacing);
    channelAbsDisplay.value = statsCurrent.maxAbs.slice();
    drawSamples(lastRenderedPosition, targetPosition, samplesCurrent, statsCurrent);
    lastRenderedPosition = targetPosition;
  }

  drawScanLine();
};

// WebSocket 数据处理器
const handleDataPacket = (packet: EegDataPacket) => {
  // 宽松匹配：支持字符串和数字类型的 nodeId
  const packetNodeId = String(packet.nodeId);
  const selectedId = selectedNodeId.value ? String(selectedNodeId.value) : null;
  
  if (!selectedId || packetNodeId !== selectedId) return;

  const windowSize = Math.max(1, timeWindowSec.value * SAMPLE_RATE);

  const pushSample = (channels: number[]) => {
    packetCount.value++;

    for (let ch = 0; ch < channelCount && ch < channels.length; ch++) {
      if (!samplesCurrent[ch]) continue;
      samplesCurrent[ch][scanPosition.value] = channels[ch];
    }

    scanPosition.value++;
    totalReceivedSamples.value++;

    if (scanPosition.value >= windowSize) {
      scanPosition.value = 0;
      isWrapped.value = true;
      scanCycle += 1;
      const prev = samplesPrev;
      samplesPrev = samplesCurrent;
      samplesCurrent = prev;
      for (let ch = 0; ch < channelCount; ch++) {
        samplesCurrent[ch]?.fill(0);
      }
    }
  };

  if (packet.samples && packet.samples.length > 0) {
    for (const channels of packet.samples) {
      pushSample(channels);
    }
  } else if (packet.channels?.length) {
    pushSample(packet.channels);
  }

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
      renderFrame();
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
let unsubConnected: (() => void) | null = null;
let unsubData: (() => void) | null = null;

console.log('[Oscilloscope] Component code loaded - v5 scan sweep mode');

// 生命周期
onMounted(async () => {
  try {
    createSamplesBuffer(DEFAULT_WINDOW_SEC * SAMPLE_RATE);
    initCanvas();

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
  resizeObserver?.disconnect();
  resizeObserver = null;
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
  resetAllData();
});

// 监听时间窗口变化
watch(timeWindowSec, () => {
  normalizeTimeWindow();
  createSamplesBuffer(timeWindowSec.value * SAMPLE_RATE);
  // 窗口大小改变时重置扫描
  scanPosition.value = 0;
  isWrapped.value = false;
  scanCycle = 0;
  lastRenderedCycle = 0;
  lastRenderedPosition = 0;
  clearWaveCanvas();
  clearOverlayCanvas();
  drawGrid();
  requestRenderFrame();
});

watch(gainFineByCh, () => {
  if (autoGainEnabled.value || isAutoGainSync) return;
  gainFineByCh.value.forEach((_, ch) => normalizeGainFine(ch));
  redrawAllSamples();
}, { deep: true });

watch(gainExpByCh, () => {
  if (autoGainEnabled.value || isAutoGainSync) return;
  gainExpByCh.value.forEach((_, ch) => normalizeGainExp(ch));
  redrawAllSamples();
}, { deep: true });

watch(canDisplay, (enabled) => {
  if (!enabled) {
    clearWaveCanvas();
    clearOverlayCanvas();
  }
});

watch(centerEnabled, () => {
  if (!centerEnabled.value && autoGainEnabled.value) {
    autoGainEnabled.value = false;
  }
  redrawAllSamples();
});

watch(autoGainEnabled, () => {
  if (autoGainEnabled.value) {
    centerEnabled.value = true;
  }
  redrawAllSamples();
});

watch(sidebarCollapsed, () => {
  updatePlotMetrics();
  drawGrid();
  redrawAllSamples();
});

const resetAllData = () => {
  scanPosition.value = 0;
  isWrapped.value = false;
  totalReceivedSamples.value = 0;
  scanCycle = 0;
  lastRenderedCycle = 0;
  lastRenderedPosition = 0;
  createSamplesBuffer(timeWindowSec.value * SAMPLE_RATE);
  packetCount.value = 0;
  autoGainDisplay.value = gainFineByCh.value.map((fine, ch) => fine * Math.pow(10, gainExpByCh.value[ch] || 0));
  channelRanges.value = Array.from({ length: channelCount }, () => ({ max: 0, min: 0 }));
  clearWaveCanvas();
  clearOverlayCanvas();
  drawGrid();
};
</script>

<style scoped>
.osc-root {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.osc-statusbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  padding-bottom: 8px;
}

.osc-status-section {
  display: flex;
  align-items: center;
  gap: 6px;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  padding: 4px 6px;
}

.osc-status-section.osc-time-section {
  padding: 2px 6px;
}

.osc-status-section.osc-status-close {
  margin-left: auto;
  padding: 2px;
  border: none;
  background: transparent;
}

.osc-toggle-button {
  min-width: 46px;
  text-transform: none;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  border-width: 0;
  box-shadow: none;
}

.osc-toggle-active {
  font-weight: 600;
}

.osc-status-label {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
}

.osc-select-source-alert {
  cursor: pointer;
  padding: 12px;
  border-radius: 8px;
}

.osc-select-source-link {
  text-decoration: underline;
  font-weight: 600;
  color: var(--v-theme-primary-base, #1e88e5);
  margin-left: 4px;
}

.osc-status-inline {
  display: flex;
  align-items: center;
  gap: 2px;
}

.osc-time-inline {
  gap: 0;
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  padding: 0 2px;
}

.osc-time-btn {
  cursor: pointer;
  user-select: none;
  padding: 0 6px;
  font-weight: 700;
  font-size: 14px;
  color: #777;
  line-height: 1;
  height: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.osc-time-btn:hover:not(.disabled) {
  background: rgba(0, 0, 0, 0.1);
  color: #333;
  border-radius: 2px;
}

.osc-time-btn.disabled {
  opacity: 0.25;
  cursor: default;
}

.osc-time-value {
  min-width: 30px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: #444;
  padding: 0 4px;
}

.osc-status-value {
  font-size: 11px;
  min-width: 36px;
  text-align: center;
  color: #333;
}


.osc-status-text {
  font-size: 11px;
  color: #444;
  white-space: nowrap;
}

@media (max-width: 1100px) {
  .osc-status-label {
    display: none;
  }
  .osc-status-text {
    font-size: 10px;
  }
}

.osc-chart-container {
  position: relative;
  height: 400px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
}

.osc-chart {
  position: relative;
  width: 100%;
  height: 100%;
}

.osc-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.osc-overlay {
  pointer-events: none;
}

.osc-sidebar {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 220px;
  border-left: 1px solid #e0e0e0;
  background: #fafafa;
  padding: 6px 4px;
  box-sizing: border-box;
  transition: width 0.2s ease;
}

.osc-sidebar.collapsed {
  width: 24px;
  padding: 6px 2px;
}

.osc-sidebar-toggle {
  position: absolute;
  top: 8px;
  left: -12px;
  width: 24px;
  height: 24px;
  border-radius: 12px;
  border: 1px solid #d0d0d0;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}

.osc-sidebar-row {
  position: absolute;
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0 6px;
  box-sizing: border-box;
}

.osc-gain-row {
  width: 100%;
}

.osc-gain-row-horizontal {
  display: flex;
  gap: 4px;
  align-items: center;
  justify-content: flex-start;
  flex-wrap: nowrap;
}

.osc-gain-mini-ctrl {
  display: flex;
  align-items: center;
  gap: 0px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 4px;
  border: 1px solid rgba(0, 0, 0, 0.05);
}

.osc-gain-btn {
  cursor: pointer;
  padding: 0 4px;
  user-select: none;
  font-weight: bold;
  font-size: 13px;
  color: #777;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 20px;
  transition: background 0.1s;
}

.osc-gain-btn:hover:not(.disabled) {
  background: rgba(0, 0, 0, 0.1);
  color: #333;
}

.osc-gain-btn.disabled {
  opacity: 0.2;
  cursor: default;
}

.osc-gain-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.osc-gain-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
}

.osc-gain-label {
  font-size: 8px;
  color: #777;
  text-align: left;
}

.osc-gain-equals {
  font-size: 10px;
  color: #444;
  white-space: nowrap;
}

.osc-gain-total {
  min-width: 34px;
  text-align: right;
  font-size: 10px;
  font-weight: 600;
  color: #444;
}

.osc-gain-value {
  min-width: 16px;
  text-align: center;
  font-size: 10px;
  font-weight: 600;
  color: #444;
  padding: 0 2px;
}

.osc-gain-total.is-auto,
.osc-gain-value.is-auto {
  color: #1e88e5;
}

.osc-left-axis {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 0;
  width: 70px;
  padding: 6px 4px;
  box-sizing: border-box;
  border-right: 1px solid #e0e0e0;
  background: #fafafa;
}

.osc-left-axis-row {
  position: absolute;
  left: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: flex-start;
  gap: 2px;
  padding: 0 4px;
  box-sizing: border-box;
  --channel-line-color: transparent;
}

.osc-left-axis-row::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  height: 1px;
  background: var(--channel-line-color);
  opacity: 0.4;
}

.osc-left-axis-label {
  font-size: 10px;
  color: #444;
}

.osc-left-axis-values {
  font-size: 9px;
  color: #666;
  line-height: 1.1;
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
</style>
