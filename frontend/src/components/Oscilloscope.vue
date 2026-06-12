<template>
  <v-card :class="{ 'osc-fullscreen-card': fullscreen }" class="mb-4" variant="tonal">

    <v-card-text class="pa-2">
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
            <div class="osc-status-text">{{ currentSampleRate }}Hz</div>
          </div>
          <div class="osc-status-section">
            <div class="osc-status-label">平均延迟</div>
            <div class="osc-status-text" :style="{ color: isNonRealtime ? '#FB8C00' : undefined }">
              {{ averageDelayMs.toFixed(1) }}ms
            </div>
            <div v-if="isNonRealtime" class="osc-status-text">非实时</div>
          </div>
          <div class="osc-status-section osc-status-close">
            <v-btn
              v-if="!fullscreen"
              size="x-small"
              variant="text"
              color="grey"
              icon="mdi-fullscreen"
              title="全屏显示"
              @click="openFullscreen"
            />
            <v-btn
              size="x-small"
              variant="text"
              color="grey"
              :icon="fullscreen ? 'mdi-fullscreen-exit' : 'mdi-close'"
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
              <div class="osc-left-axis-label">{{ getChannelDisplayName(ch - 1) }}</div>
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
import { useRoute, useRouter } from 'vue-router';
import { sessionStore } from '../services/sessionStore';
import { eegWebSocket, type EegDataPacket } from '../services/websocket';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';

const props = defineProps<{
  initialNodeId?: string;
  fullscreen?: boolean;
}>();

const emit = defineEmits<{
  (e: 'remove'): void;
}>();

const router = useRouter();
const route = useRoute();

// 配置
const channelCount = ref(8);
const channelNames = ref<string[]>(Array.from({ length: 8 }, (_, i) => `CH${i + 1}`));
const colors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];

// === 扫描模式配置 ===
const currentSampleRate = ref(1000);
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

// 性能优化：目标刷新率 60fps
const TARGET_FPS = 60;
const FRAME_INTERVAL = 1000 / TARGET_FPS;
const MAX_DISPLAY_LAG_MS = 250;

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
const gainFineByCh = ref<number[]>(Array.from({ length: channelCount.value }, () => 1.0));
const gainExpByCh = ref<number[]>(Array.from({ length: channelCount.value }, () => 0));
const autoGainDisplay = ref<number[]>(Array.from({ length: channelCount.value }, () => 1));
const centerEnabled = ref(false);
const isDebugAutoGainDefault = computed(() => {
  const debugFlag = String(route.query.debug || '').toLowerCase();
  const traceTag = String(route.query._t || '').toLowerCase();
  return debugFlag === '1' || debugFlag === 'true' || traceTag.includes('debug');
});
const autoGainEnabled = ref(isDebugAutoGainDefault.value);
let isAutoGainSync = false;
const channelAbsDisplay = ref<number[]>(Array.from({ length: channelCount.value }, () => 1));
const sidebarCollapsed = ref(false);
const sourceDialogOpen = ref(false);
const channelRanges = ref<Array<{ max: number; min: number }>>(Array.from({ length: channelCount.value }, () => ({ max: 0, min: 0 })));

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
let latestDataTimestamp = 0;
let latestDataWallTime = 0;

type RunningChannelStats = {
  count: number;
  sum: number[];
  rawMax: number[];
  rawMin: number[];
};

const createEmptyRunningStats = (): RunningChannelStats => ({
  count: 0,
  sum: new Array(channelCount.value).fill(0),
  rawMax: new Array(channelCount.value).fill(-Infinity),
  rawMin: new Array(channelCount.value).fill(Infinity),
});

let statsCurrentRunning: RunningChannelStats = createEmptyRunningStats();
let statsPrevRunning: RunningChannelStats = createEmptyRunningStats();

// 数据源
const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);
const processingDelayMs = ref(0);
const isNonRealtime = ref(false);
// ========== 图状态：通过 sessionStore 全局订阅 — 无需组件轮询。 ==========

// 延迟历史数据
const delayHistory = ref<Array<{timestamp: number, delay: number}>>([]); // 存储最近1秒的延迟数据
const averageDelayMs = ref(0); // 最近1秒的平均延迟

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

const getChannelDisplayName = (ch: number) => {
  return channelNames.value[ch] || `CH${ch + 1}`;
};

const ensureChannelSchema = (count: number, names?: string[]) => {
  const normalizedCount = Math.max(1, Math.floor(Number(count) || 1));
  const normalizedNames = Array.from({ length: normalizedCount }, (_, i) => {
    return names?.[i] || channelNames.value[i] || `CH${i + 1}`;
  });

  const namesChanged = normalizedNames.some((name, i) => name !== channelNames.value[i]);

  if (channelCount.value === normalizedCount && !namesChanged) {
    return;
  }

  channelCount.value = normalizedCount;
  channelNames.value = normalizedNames;
  gainFineByCh.value = Array.from({ length: normalizedCount }, (_, i) => gainFineByCh.value[i] ?? 1.0);
  gainExpByCh.value = Array.from({ length: normalizedCount }, (_, i) => gainExpByCh.value[i] ?? 0);
  autoGainDisplay.value = Array.from({ length: normalizedCount }, (_, i) => autoGainDisplay.value[i] ?? 1);
  channelAbsDisplay.value = Array.from({ length: normalizedCount }, (_, i) => channelAbsDisplay.value[i] ?? 1);
  channelRanges.value = Array.from({ length: normalizedCount }, (_, i) => channelRanges.value[i] || { max: 0, min: 0 });
  resetAllData();
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
  const bound = sessionStore.getViewBoundNode(viewId);
  return !!bound && bound === nodeId;
};

const onNodeSelected = (nodeId: string | null) => {
  console.log('[Oscilloscope] Node selected:', nodeId, 'viewId:', viewId);
  if (nodeId) {
    sessionStore.bindViewToNode(viewId, nodeId);
    selectedNodeId.value = nodeId;

    const node = graphNodes.value.find((n) => n.id === nodeId);
    const paramNames = Array.isArray(node?.params?.availableChannels)
      ? (node?.params?.availableChannels as unknown[]).map((name, idx) => String(name || `CH${idx + 1}`))
      : null;
    if (paramNames && paramNames.length > 0) {
      ensureChannelSchema(paramNames.length, paramNames);
    }

    subscribeToNode(nodeId);
    sourceDialogOpen.value = false;
  } else {
    sessionStore.bindViewToNode(viewId, null);
    selectedNodeId.value = null;
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

const openFullscreen = () => {
  if (!selectedNodeId.value) return;
  const routeData = router.resolve({
    name: 'Fullscreen',
    params: { type: 'osc', nodeId: selectedNodeId.value }
  });
  window.open(routeData.href, '_blank');
};

const createSamplesBuffer = (windowSize: number) => {
  const size = Math.max(1, windowSize);
  samplesCurrent = Array.from({ length: channelCount.value }, () => new Array(size).fill(0));
  samplesPrev = Array.from({ length: channelCount.value }, () => new Array(size).fill(0));
  statsCurrentRunning = createEmptyRunningStats();
  statsPrevRunning = createEmptyRunningStats();
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
  const channelSpacing = channelCount.value > 0 ? plotHeight / (channelCount.value + 0.5) : 0;
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

  for (let ch = 0; ch < channelCount.value; ch++) {
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
  for (let ch = 0; ch < channelCount.value; ch++) {
    const y = top + channelSpacing * (ch + 0.5);
    gridCtx.fillText(getChannelDisplayName(ch), left - 8, y);
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

// Scan line removed: overlay canvas retained for potential future overlays

type ChannelStats = {
  means: number[];
  maxAbs: number[];
  rawMax: number[];
  rawMin: number[];
};

const buildChannelStats = (running: RunningChannelStats): ChannelStats => {
  const means = new Array(channelCount.value).fill(0);
  const maxAbs = new Array(channelCount.value).fill(1);
  const rawMax = new Array(channelCount.value).fill(0);
  const rawMin = new Array(channelCount.value).fill(0);

  const count = running.count;
  if (count <= 0) {
    return {
      means,
      maxAbs,
      rawMax,
      rawMin,
    };
  }

  for (let ch = 0; ch < channelCount.value; ch++) {
    const mean = (running.sum[ch] || 0) / count;
    means[ch] = mean;

    const max = Number.isFinite(running.rawMax[ch]) ? running.rawMax[ch] : 0;
    const min = Number.isFinite(running.rawMin[ch]) ? running.rawMin[ch] : 0;
    rawMax[ch] = max;
    rawMin[ch] = min;

    const peak = centerEnabled.value
      ? Math.max(Math.abs(max - mean), Math.abs(min - mean))
      : Math.max(Math.abs(max), Math.abs(min));
    maxAbs[ch] = peak || 1;
  }

  return {
    means,
    maxAbs,
    rawMax,
    rawMin,
  };
};

const syncAutoGainDisplay = (stats: ChannelStats, channelSpacing: number) => {
  if (!autoGainEnabled.value) return;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;
  const amplitudeScale = plotMetrics.value.amplitudeScale || 1;

  isAutoGainSync = true;
  for (let ch = 0; ch < channelCount.value; ch++) {
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
  const windowSize = Math.max(1, timeWindowSec.value * currentSampleRate.value);
  const baseX = (pos: number) => left + (plotWidth * pos) / (windowSize - 1 || 1);
  const useAuto = autoGainEnabled.value;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;

  for (let ch = 0; ch < channelCount.value; ch++) {
    waveCtx.strokeStyle = colors[ch];
    waveCtx.lineWidth = 1.5;
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
  const windowSize = Math.max(1, timeWindowSec.value * currentSampleRate.value);
  const statsCurrent = buildChannelStats(statsCurrentRunning);
  const statsPrev = isWrapped.value ? buildChannelStats(statsPrevRunning) : buildChannelStats(createEmptyRunningStats());

  clearWaveCanvas();

  const { left, top, width: plotWidth, channelSpacing, amplitudeScale } = plotMetrics.value;
  const baseX = (pos: number) => left + (plotWidth * pos) / (windowSize - 1 || 1);
  const useAuto = autoGainEnabled.value;
  const targetHalfHeight = (channelSpacing * 0.5) / 1.1;

  syncAutoGainDisplay(statsCurrent, channelSpacing);
  updateChannelRange(statsCurrent);
  channelAbsDisplay.value = statsCurrent.maxAbs.slice();

  for (let ch = 0; ch < channelCount.value; ch++) {
    waveCtx.strokeStyle = colors[ch];
    waveCtx.lineWidth = 1.5;
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
};

const renderFrame = () => {
  if (!canDisplay.value) return;
  const statsCurrent = buildChannelStats(statsCurrentRunning);
  updateChannelRange(statsCurrent);

  if (lastRenderedCycle !== scanCycle) {
    lastRenderedCycle = scanCycle;
    lastRenderedPosition = 0;
    drawFullWindow();
  }

  const { left, top, width: plotWidth, height: plotHeight } = plotMetrics.value;
  const sr = currentSampleRate.value;
  const windowSize = Math.max(1, timeWindowSec.value * sr);
  const baseX = (pos: number) => left + (plotWidth * pos) / (windowSize - 1 || 1);

  const targetPosition = scanPosition.value;
  if (targetPosition > lastRenderedPosition) {
    syncAutoGainDisplay(statsCurrent, plotMetrics.value.channelSpacing);
    channelAbsDisplay.value = statsCurrent.maxAbs.slice();
    
    // 清除即将绘制的区域，防止与旧周期数据重叠
    if (waveCtx) {
      const x1 = baseX(lastRenderedPosition);
      const x2 = baseX(targetPosition);
      // 仅清除目标区域，不带额外边距，避免破坏已绘制的数据
      waveCtx.clearRect(x1, top, x2 - x1, plotHeight);
    }

    // 增加回溯点，确保新旧线段完美衔接，并修复刚才可能因 clearRect 被微量擦除的边缘
    const lookback = Math.min(lastRenderedPosition, 5);
    drawSamples(lastRenderedPosition - lookback, targetPosition, samplesCurrent, statsCurrent);
    lastRenderedPosition = targetPosition;
  }

  // 清除扫描线周围的间隙，确保视觉上不会有新旧交替的重叠感
  if (waveCtx) {
    const elapsedSec = (performance.now() - latestDataWallTime) / 1000;
    const estimatedDataTime = (latestDataTimestamp / 1000) + elapsedSec;
    const displayPos = Math.floor((estimatedDataTime * sr) % windowSize);
    
    // 清除从当前数据末尾到预测扫描线位置后方的一段距离
    const gapSamples = Math.max(sr * 0.1, Math.floor(windowSize * 0.02)); 
    const clearStart = targetPosition;
    const clearEnd = (displayPos + gapSamples) % windowSize;
    
    const xStart = baseX(clearStart);
    const xEnd = baseX(clearEnd);
    
    if (xEnd > xStart) {
      waveCtx.clearRect(xStart, top, xEnd - xStart, plotHeight);
    } else if (xEnd < xStart) {
      waveCtx.clearRect(xStart, top, (left + plotWidth) - xStart, plotHeight);
      waveCtx.clearRect(left, top, xEnd - left, plotHeight);
    }
  }

};

// WebSocket 数据处理器
// 更新延迟历史数据
const updateDelayHistory = (delayMs: number) => {
  const now = Date.now();
  
  // 添加新延迟数据
  delayHistory.value.push({ timestamp: now, delay: delayMs });
  
  // 移除超过1秒的旧数据
  const oneSecondAgo = now - 1000;
  delayHistory.value = delayHistory.value.filter(item => item.timestamp >= oneSecondAgo);
  
  // 计算平均延迟
  if (delayHistory.value.length > 0) {
    const totalDelay = delayHistory.value.reduce((sum, item) => sum + item.delay, 0);
    averageDelayMs.value = totalDelay / delayHistory.value.length;
  } else {
    averageDelayMs.value = 0;
  }
};

const handleDataPacket = (packet: EegDataPacket) => {
  const packetNodeId = String(packet.nodeId);
  const selectedId = selectedNodeId.value ? String(selectedNodeId.value) : null;

  if (!selectedId || packetNodeId !== selectedId) {
    // 仅在 ID 不匹配且两个 ID 都非空时警告，帮助诊断跳变问题
    if (selectedId && packetNodeId && packetNodeId !== 'undefined' && selectedId !== 'undefined') {
      console.warn(`[Oscilloscope] Mismatched packet nodeId="${packetNodeId}" vs selected="${selectedId}" — filtered out`);
    }
    return;
  }

  console.log(`[Oscilloscope] Matched packet nodeId="${packetNodeId}" channels=${packet.channels?.length} names=${JSON.stringify(packet.channelNames?.slice(0, 3))}`);

  isGraphFrozen.value = true;

  processingDelayMs.value = Math.max(0, Number(packet.processingDelayMs || 0));
  isNonRealtime.value = Boolean(packet.nonRealtime || processingDelayMs.value > 10000);
  
  // 更新延迟历史数据
  updateDelayHistory(processingDelayMs.value);

  const inferredCount = Math.max(
    Array.isArray(packet.channelNames) ? packet.channelNames.length : 0,
    Array.isArray(packet.channels) ? packet.channels.length : 0,
    1,
  );
  const inferredNames = Array.isArray(packet.channelNames)
    ? packet.channelNames.map((name, idx) => String(name || `CH${idx + 1}`))
    : undefined;
  ensureChannelSchema(inferredCount, inferredNames);

  // 如果包中带有采样率信息，则更新
  if (packet.sampleRate && packet.sampleRate > 0 && packet.sampleRate !== currentSampleRate.value) {
    currentSampleRate.value = packet.sampleRate;
    resetAllData();
  }

  const sr = currentSampleRate.value;
  const windowSize = Math.max(1, timeWindowSec.value * sr);
  
  // 核心逻辑：基于时间戳确定扫描位置，确保时间流速一致且优先绘制最新数据
  // 如果没有时间戳，则使用当前现实时间
  const timestamp = packet.utcFirstFrameMs || packet.timestamp || Date.now();
  
  // 更新最新数据时间点，用于扫描线平滑估计
  latestDataTimestamp = timestamp;
  latestDataWallTime = performance.now();
  
  // 计算基于时间戳的全局偏移量
  const globalSampleIndex = Math.floor((timestamp / 1000) * sr);
  const targetCycle = Math.floor(globalSampleIndex / windowSize);
  const targetPos = globalSampleIndex % windowSize;

  // 1. 处理周期同步（Sweep/Wrap 逻辑）
  if (targetCycle > scanCycle) {
    // 数据进入了新的周期，执行缓冲区切换
    // 如果跳过了多个周期，我们也只保留最新的
    const gap = targetCycle - scanCycle;
    for (let i = 0; i < Math.min(gap, 2); i++) {
      isWrapped.value = true;
      scanCycle += 1;
      const prev = samplesPrev;
      samplesPrev = samplesCurrent;
      samplesCurrent = prev;

      // 为新的一轮清理数据
      for (let ch = 0; ch < channelCount.value; ch++) {
        samplesCurrent[ch]?.fill(0);
      }

      // 同步统计信息
      statsPrevRunning = { ...statsCurrentRunning };
      statsCurrentRunning = createEmptyRunningStats();
    }
    scanCycle = targetCycle;
  } else if (targetCycle < scanCycle) {
    // 丢弃过旧的包（属于过去的某个扫描周期）
    return;
  }

  // 2. 将数据插入到基于时间戳确定的准确索引处
  const pushSampleAt = (channels: number[], pos: number) => {
    packetCount.value++;
    const idx = pos % windowSize;

    for (let ch = 0; ch < channelCount.value; ch++) {
      if (!samplesCurrent[ch]) continue;
      const value = channels[ch] ?? 0;
      samplesCurrent[ch][idx] = value;

      statsCurrentRunning.sum[ch] += value;
      if (value > statsCurrentRunning.rawMax[ch]) statsCurrentRunning.rawMax[ch] = value;
      if (value < statsCurrentRunning.rawMin[ch]) statsCurrentRunning.rawMin[ch] = value;
    }
    statsCurrentRunning.count += 1;
    totalReceivedSamples.value++;
  };

  // 不再使用“复制上一点”补样，避免在真实设备链路抖动时人为制造水平离散线。

  if (packet.samples && packet.samples.length > 0) {
    // 批量模式：顺序从起始 targetPos 开始填充
    for (let i = 0; i < packet.samples.length; i++) {
      pushSampleAt(packet.samples[i], targetPos + i);
    }
    // 扫描线位置更新为这批数据的末尾
    scanPosition.value = (targetPos + packet.samples.length) % windowSize;
  } else if (packet.channels?.length) {
    // 单样点模式
    pushSampleAt(packet.channels, targetPos);
    scanPosition.value = (targetPos + 1) % windowSize;
  }

  // 积压检查：如果计算出的位置落后现实太多，说明渲染压力大，强制刷新扫描线位置
  const wallClockPos = Math.floor(((Date.now() / 1000) % timeWindowSec.value) * sr);
  // 如果差异超过 200ms
  if (Math.abs(wallClockPos - scanPosition.value) > sr * 0.2) {
    // 仅在数据正常流动时，才考虑强制同步扫描线到现实时间
    // 但为了避免抖动，通常还是以最新数据的 timestamp 为主
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

// 清理函数
let unsubConnected: (() => void) | null = null;
let unsubData: (() => void) | null = null;
let unsubStore: (() => void) | null = null;

console.log('[Oscilloscope] Component code loaded - v5 scan sweep mode');

// ========== localStorage 持久化 ==========
const STORAGE_PREFIX = 'osc_settings_';

interface OscSettings {
  timeWindowSec: number;
  centerEnabled: boolean;
  autoGainEnabled: boolean;
  sidebarCollapsed: boolean;
  gainFineByCh: number[];
  gainExpByCh: number[];
}

const getStorageKey = () => {
  // 使用选中节点ID作为存储键，如果没有则使用全局键
  const nodeId = selectedNodeId.value;
  return nodeId ? `${STORAGE_PREFIX}${nodeId}` : `${STORAGE_PREFIX}global`;
};

const loadSettings = () => {
  try {
    // 先尝试加载节点专用设置
    let key = getStorageKey();
    let raw = localStorage.getItem(key);
    // 如果节点专用设置不存在，尝试加载全局默认设置
    if (!raw && selectedNodeId.value) {
      raw = localStorage.getItem(`${STORAGE_PREFIX}global`);
    }
    if (!raw) return;
    const saved: Partial<OscSettings> = JSON.parse(raw);
    if (typeof saved.timeWindowSec === 'number') {
      timeWindowSec.value = saved.timeWindowSec;
    }
    if (typeof saved.centerEnabled === 'boolean') {
      centerEnabled.value = saved.centerEnabled;
    }
    if (typeof saved.autoGainEnabled === 'boolean') {
      autoGainEnabled.value = saved.autoGainEnabled;
    }
    if (typeof saved.sidebarCollapsed === 'boolean') {
      sidebarCollapsed.value = saved.sidebarCollapsed;
    }
    if (Array.isArray(saved.gainFineByCh)) {
      for (let i = 0; i < Math.min(saved.gainFineByCh.length, gainFineByCh.value.length); i++) {
        gainFineByCh.value[i] = saved.gainFineByCh[i];
      }
    }
    if (Array.isArray(saved.gainExpByCh)) {
      for (let i = 0; i < Math.min(saved.gainExpByCh.length, gainExpByCh.value.length); i++) {
        gainExpByCh.value[i] = saved.gainExpByCh[i];
      }
    }
  } catch (e) {
    console.warn('[Oscilloscope] Failed to load settings:', e);
  }
};

let saveTimer: ReturnType<typeof setTimeout> | null = null;
const saveSettings = () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      const settings: OscSettings = {
        timeWindowSec: timeWindowSec.value,
        centerEnabled: centerEnabled.value,
        autoGainEnabled: autoGainEnabled.value,
        sidebarCollapsed: sidebarCollapsed.value,
        gainFineByCh: [...gainFineByCh.value],
        gainExpByCh: [...gainExpByCh.value],
      };
      // 同时保存到节点专用键和全局键
      localStorage.setItem(getStorageKey(), JSON.stringify(settings));
      // 如果当前有关联节点，也更新全局设置作为后续新节点的默认值
      if (selectedNodeId.value) {
        localStorage.setItem(`${STORAGE_PREFIX}global`, JSON.stringify(settings));
      }
    } catch (e) {
      console.warn('[Oscilloscope] Failed to save settings:', e);
    }
    saveTimer = null;
  }, 300);
};

// 生命周期
onMounted(async () => {
  try {
    // 从 localStorage 恢复设置（在初始化之前）
    loadSettings();

    createSamplesBuffer(timeWindowSec.value * currentSampleRate.value);
    initCanvas();

    // 从 sessionStore 获取初始图状态
    const graph = sessionStore.getGraph();
    graphNodes.value = graph.nodes || [];
    isGraphFrozen.value = graph.frozen || false;

    // 恢复绑定的节点
    try {
      const bound = sessionStore.getViewBoundNode(viewId);
      if (bound) {
        selectedNodeId.value = bound;
      }
    } catch (e) {
      console.warn('[Oscilloscope] Failed to restore bound node:', e);
    }

    // 订阅 sessionStore 全局状态，替代独立的 graphState 轮询
    unsubStore = sessionStore.subscribe((state) => {
      graphNodes.value = state.graph.nodes || [];
      isGraphFrozen.value = state.graph.frozen || false;
    });

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
  unsubStore?.();
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
  // 切换节点时清空数据并尝试加载新节点的设置
  resetAllData();
  if (newId) {
    loadSettings();
    createSamplesBuffer(timeWindowSec.value * currentSampleRate.value);
  }
});

// 监听时间窗口变化
watch(timeWindowSec, () => {
  normalizeTimeWindow();
  saveSettings();
  createSamplesBuffer(timeWindowSec.value * currentSampleRate.value);
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
  saveSettings();
  redrawAllSamples();
}, { deep: true });

watch(gainExpByCh, () => {
  if (autoGainEnabled.value || isAutoGainSync) return;
  gainExpByCh.value.forEach((_, ch) => normalizeGainExp(ch));
  saveSettings();
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
  saveSettings();
  redrawAllSamples();
});

watch(autoGainEnabled, () => {
  if (autoGainEnabled.value) {
    centerEnabled.value = true;
  }
  saveSettings();
  redrawAllSamples();
});

watch(sidebarCollapsed, () => {
  saveSettings();
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
  latestDataTimestamp = 0;
  latestDataWallTime = 0;
  createSamplesBuffer(timeWindowSec.value * currentSampleRate.value);
  packetCount.value = 0;
  processingDelayMs.value = 0;
  isNonRealtime.value = false;
  autoGainDisplay.value = gainFineByCh.value.map((fine, ch) => fine * Math.pow(10, gainExpByCh.value[ch] || 0));
  channelRanges.value = Array.from({ length: channelCount.value }, () => ({ max: 0, min: 0 }));
  clearWaveCanvas();
  clearOverlayCanvas();
  drawGrid();
};
</script>

<style scoped>
.osc-root {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
  min-width: 320px;
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
  height: 400px; /* Fixed height for card mode */
  min-height: 200px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  width: 100%;
}

.osc-fullscreen-card {
  height: 100% !important;
  width: 100% !important;
  margin: 0 !important;
  display: flex !important;
  flex-direction: column !important;
  border-radius: 0 !important;
}

.osc-fullscreen-card :deep(.v-card-text) {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
  padding: 8px !important;
}

.osc-fullscreen-card .osc-root {
  flex: 1 !important;
  display: flex !important;
  flex-direction: column !important;
}

.osc-fullscreen-card .osc-chart-container {
  height: auto !important;
  flex: 1 !important;
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
