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
        @click="settingsDialogOpen = true"
      >
        <div>
          请从上方下拉菜单选择计算图中的节点作为数据源。
          <span class="osc-select-source-link">配置信号源</span>
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
            <div class="osc-status-label">窗口时间</div>
            <div class="osc-status-inline osc-time-inline">
              <span
                class="osc-time-btn"
                :class="{ disabled: !canDisplay }"
                @click="canDisplay && stepWindowSec(-0.1)"
              >-</span>
              <span class="osc-time-value">{{ fftWindowSec.toFixed(1) }}s</span>
              <span
                class="osc-time-btn"
                :class="{ disabled: !canDisplay }"
                @click="canDisplay && stepWindowSec(0.1)"
              >+</span>
            </div>
          </div>

          <div class="osc-status-section osc-status-source">
            <v-btn
              size="x-small"
              variant="outlined"
              @click="settingsDialogOpen = true"
            >
              {{ signalSourceButtonText }}
            </v-btn>
            <v-chip size="x-small" :color="statusColor">
              <v-icon left size="x-small">{{ statusIcon }}</v-icon>
              {{ statusText }}
            </v-chip>
          </div>

          <div class="osc-status-section osc-status-average">
            <div class="osc-status-label">通道</div>
            <div class="osc-status-text">
              {{ channelDisplayText }}
              <span v-if="averageEnabled" class="text-caption text-success">({{ averageDisplayText }})</span>
            </div>
            <v-btn
              size="x-small"
              variant="outlined"
              class="ml-2"
              @click="channelDialogOpen = true"
            >
              设置
            </v-btn>
            <v-chip
              size="x-small"
              :color="averageEnabled ? 'primary' : 'grey'"
              variant="tonal"
              class="ml-2"
              @click="averageEnabled = !averageEnabled"
            >
              平均 {{ averageEnabled ? '开' : '关' }}
            </v-chip>
          </div>

          <div class="osc-status-section">
            <div class="osc-status-label">显示模式</div>
            <v-btn-toggle v-model="displayMode" mandatory density="compact" variant="outlined">
              <v-btn size="x-small" value="spectrum">频谱</v-btn>
              <v-btn size="x-small" value="spectrogram">时频谱</v-btn>
            </v-btn-toggle>
          </div>

          <div class="osc-status-section">
            <div class="osc-status-label">采样率</div>
            <div class="osc-status-text">{{ sampleRate }}Hz</div>
          </div>

          <div class="osc-status-section">
            <div class="osc-status-label">频率范围</div>
            <div class="osc-status-text">{{ freqRange[0] }}-{{ freqRange[1] }}Hz</div>
          </div>

          <div class="osc-status-section">
            <div class="osc-status-label">平均延迟</div>
            <div class="osc-status-text">{{ averageDelayMs.toFixed(1) }}ms</div>
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

        <v-dialog v-model="settingsDialogOpen" max-width="460">
          <v-card>
            <v-card-title>频谱显示设置</v-card-title>
            <v-divider />
            <v-card-text class="pt-4">
              <div class="text-subtitle-2 mb-2">选择数据源节点</div>
              <v-list density="compact" class="border rounded mb-4" max-height="200">
                <v-list-item
                  v-for="node in availableOscNodes"
                  :key="node.id"
                  @click="onNodeSelected(node.id)"
                  :active="selectedNodeId === node.id"
                  color="primary"
                >
                  <template #prepend>
                    <v-icon size="small">{{ node.type === 'SPECTRUM' ? 'mdi-chart-bell-curve' : 'mdi-waveform' }}</v-icon>
                  </template>
                  <v-list-item-title>{{ node.name || node.id }}</v-list-item-title>
                  <template #append>
                    <v-chip v-if="selectedNodeId === node.id" size="x-small" color="primary">已选择</v-chip>
                  </template>
                </v-list-item>
                <v-list-item v-if="availableOscNodes.length === 0" disabled>
                  <v-list-item-title>无可用节点</v-list-item-title>
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
              <v-btn size="small" variant="text" @click="settingsDialogOpen = false">关闭</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <v-dialog v-model="channelDialogOpen" max-width="460">
          <v-card>
            <v-card-title>通道设置</v-card-title>
            <v-divider />
            <v-card-text class="pt-4">
              <div class="text-subtitle-2 mb-2">选择通道</div>
              <v-btn-toggle
                v-model="selectedChannels"
                multiple
                color="primary"
                variant="outlined"
                density="compact"
                class="flex-wrap"
              >
                <v-btn
                  v-for="item in channelItems"
                  :key="`channel-${item.value}`"
                  :value="item.value"
                  size="small"
                >
                  {{ item.title }}
                </v-btn>
              </v-btn-toggle>
              <v-switch
                v-model="averageEnabled"
                label="平均"
                class="mt-2"
                density="compact"
              />
            </v-card-text>
            <v-card-actions class="justify-end">
              <v-btn size="small" variant="text" @click="channelDialogOpen = false">关闭</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <div ref="chartContainerRef" class="osc-chart-container">
          <div class="osc-chart">
            <canvas ref="gridCanvasRef" class="osc-canvas" aria-hidden="true"></canvas>
            <canvas
              ref="spectrumCanvasRef"
              class="osc-canvas"
              :class="{ 'osc-canvas-hidden': displayMode !== 'spectrum' }"
              aria-hidden="true"
            ></canvas>
            <canvas
              ref="spectrogramCanvasRef"
              class="osc-canvas"
              :class="{ 'osc-canvas-hidden': displayMode !== 'spectrogram' }"
              aria-hidden="true"
            ></canvas>
            <canvas
              ref="spectrogramOverlayCanvasRef"
              class="osc-canvas"
              :class="{ 'osc-canvas-hidden': displayMode !== 'spectrogram' }"
              aria-hidden="true"
            ></canvas>
          </div>

          <!-- 无数据遮罩 -->
          <div v-if="!canDisplay" class="no-data-overlay">
            <v-icon size="48" color="grey-lighten-1">mdi-chart-bell-curve</v-icon>
            <div class="text-h6 mt-2">{{ noDataText }}</div>
          </div>

          <!-- 缓冲中遮罩 -->
          <div v-else-if="!hasSpectrumData" class="no-data-overlay buffering-overlay">
            <v-progress-circular indeterminate color="primary" size="32" width="3" class="mb-2" />
            <div class="text-h6">缓冲中...</div>
            <div class="text-caption">{{ sampleCount }} / {{ requiredSamples }} 点</div>
          </div>
        </div>

        <div v-if="canDisplay" class="freq-datazoom-wrap px-4 py-3">
          <div 
            class="freq-datazoom-inner" 
            ref="zoomOuterRef"
            @mousedown="onZoomMouseDown"
          >
            <canvas ref="previewCanvasRef" class="zoom-preview-canvas"></canvas>
            <!-- 选中区域的高亮框 -->
            <div class="zoom-selection-mask" :style="selectionBoxStyle">
              <div class="zoom-handle left" @mousedown.stop="onHandleMouseDown($event, 'left')">
                <div class="handle-line"></div>
              </div>
              <div class="zoom-handle right" @mousedown.stop="onHandleMouseDown($event, 'right')">
                <div class="handle-line"></div>
              </div>
            </div>
          </div>
          <div class="d-flex align-center justify-space-between mt-2">
            <span class="text-caption text-grey">频率范围预览 (0 - {{ maxDisplayFreq }} Hz)</span>
            <div class="d-flex align-center gap-2">
              <span class="text-caption font-weight-bold text-primary">{{ freqRange[0] }} - {{ freqRange[1] }} Hz</span>
              <v-btn size="x-small" variant="text" color="grey" icon="mdi-refresh" @mousedown.stop="resetFreqRange" title="重置范围" />
            </div>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { eegWebSocket, type EegDataPacket } from '../services/websocket';
import { sessionStore } from '../services/sessionStore';
import type { GraphNode } from '../services/graph';

const emit = defineEmits<{
  (e: 'remove'): void;
}>();

const props = defineProps<{
  initialNodeId?: string;
  fullscreen?: boolean;
}>();

const router = useRouter();

const MAX_FREQ_LIMIT = 500;
const channelColors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];
const heatmapPalette = [
  '#313695',
  '#4575b4',
  '#74add1',
  '#abd9e9',
  '#e0f3f8',
  '#ffffbf',
  '#fee090',
  '#fdae61',
  '#f46d43',
  '#d73027',
  '#a50026',
];

const viewId = `freq-view-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

const chartContainerRef = ref<HTMLDivElement | null>(null);
const gridCanvasRef = ref<HTMLCanvasElement | null>(null);
const spectrumCanvasRef = ref<HTMLCanvasElement | null>(null);
const spectrogramCanvasRef = ref<HTMLCanvasElement | null>(null);
const spectrogramOverlayCanvasRef = ref<HTMLCanvasElement | null>(null);
const previewCanvasRef = ref<HTMLCanvasElement | null>(null);
const zoomOuterRef = ref<HTMLDivElement | null>(null);

let gridCtx: CanvasRenderingContext2D | null = null;
let spectrumCtx: CanvasRenderingContext2D | null = null;
let spectrogramCtx: CanvasRenderingContext2D | null = null;
let spectrogramOverlayCtx: CanvasRenderingContext2D | null = null;
let previewCtx: CanvasRenderingContext2D | null = null;
let resizeObserver: ResizeObserver | null = null;
let renderFrameId = 0;

const TARGET_FPS = 60;
const FRAME_INTERVAL = 1000 / TARGET_FPS;
const MAX_DISPLAY_LAG_MS = 250;
let lastRenderTime = 0;
let isRenderPending = false;
let lastFramePos: number | null = null;
let lastDataTimestamp = 0;
let lastDataWallTime = 0;

const settingsDialogOpen = ref(false);
const channelDialogOpen = ref(false);
const sampleRate = ref(1000);
const fftWindowSec = ref(1.0);
const freqRange = ref<[number, number]>([0, 125]);
const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

// 延迟相关状态
const processingDelayMs = ref(0);
const delayHistory = ref<Array<{timestamp: number, delay: number}>>([]); // 存储最近1秒的延迟数据
const averageDelayMs = ref(0); // 最近1秒的平均延迟
let delayHistoryTimer: number | null = null;

const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
// ========== 图状态：通过 sessionStore 全局订阅 — 无需组件轮询。 ==========
const channelCount = ref(8);
const channelNames = ref<string[]>(Array.from({ length: 8 }, (_, i) => `CH${i + 1}`));

const selectedChannels = ref<number[]>([0]);
const averageEnabled = ref(false);
const displayMode = ref<'spectrum' | 'spectrogram'>('spectrum');
const packetCount = ref(0);
const spectra = ref<Array<{ channel: number; mags: number[]; color: string }>>([]);
const previewSpectrum = ref<number[]>([]);
const backendSpectra = ref<number[][]>([]);
const backendAverageSpectrum = ref<number[]>([]);
const backendFftSize = ref(512);
const backendFreqResolution = ref(1000 / 512);
const spectrogramRows = ref<number[][]>([]);
const spectrogramRowsByChannel = ref<Record<number, number[][]>>({});
const spectrogramHistorySec = ref(10);
const bufferFill = ref(0);
const spectrogramPendingFrames = ref<Array<{ timestamp: number; avg?: number[]; channels: Record<number, number[]> }>>([]);
const spectrogramScanPos = ref(0);
const spectrogramLayoutKey = ref('');

const canvasSize = ref({ width: 0, height: 0, dpr: 1 });
const plotMetrics = ref({ left: 46, right: 12, top: 12, bottom: 24, width: 0, height: 0 });

const isDragging = ref<'box' | 'left' | 'right' | null>(null);
let dragStartX = 0;
let initialFreqRange: [number, number] = [0, 0];

const requiredSamples = computed(() => Math.max(8, backendFftSize.value));
const maxDisplayFreq = computed(() => Math.min(MAX_FREQ_LIMIT, Math.floor(sampleRate.value / 2)));

const sampleCount = computed(() => bufferFill.value);

const availableOscNodes = computed(() => graphNodes.value.filter((n) => n.type === 'OSC' || n.type === 'SPECTRUM'));

const channelItems = computed(() => {
  return Array.from({ length: channelCount.value }, (_, i) => ({
    title: channelNames.value[i] || `CH${i + 1}`,
    value: i,
  }));
});

const canDisplay = computed(() => Boolean(selectedNodeId.value && isGraphFrozen.value && wsStatus.value === 'connected'));

const statusText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  if (!isGraphFrozen.value) return '未冻结';
  if (wsStatus.value === 'connected') return packetCount.value > 0 ? '接收中' : '等待数据';
  if (wsStatus.value === 'connecting') return '连接中';
  if (wsStatus.value === 'error') return '错误';
  return '离线';
});

const statusColor = computed(() => {
  if (!selectedNodeId.value) return 'grey';
  if (!isGraphFrozen.value) return 'warning';
  if (wsStatus.value === 'connected') return packetCount.value > 0 ? 'success' : 'info';
  if (wsStatus.value === 'connecting') return 'info';
  if (wsStatus.value === 'error') return 'error';
  return 'grey';
});

const statusIcon = computed(() => {
  if (statusColor.value === 'success') return 'mdi-check-circle';
  if (statusColor.value === 'warning') return 'mdi-alert';
  if (statusColor.value === 'error') return 'mdi-alert-circle';
  if (statusColor.value === 'info') return 'mdi-sync';
  return 'mdi-help-circle';
});

const signalSourceButtonText = computed(() => {
  if (!selectedNodeId.value) return '信号源: 未选择';
  const node = graphNodes.value.find((n) => n.id === selectedNodeId.value);
  return `信号源: ${node?.name || selectedNodeId.value}`;
});

const noDataText = computed(() => {
  if (!selectedNodeId.value) return '请配置信号源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  if (wsStatus.value !== 'connected') return '等待服务连接';
  return '等待实时数据';
});

const channelDisplayText = computed(() => {
  if (selectedChannels.value.length === 0) return channelNames.value[0] || 'CH1';
  return selectedChannels.value.map((ch) => channelNames.value[ch] || `CH${ch + 1}`).join(', ');
});

const averageDisplayText = computed(() => `均值 ${selectedChannels.value.length} 通道`);

const selectionBoxStyle = computed(() => {
  const total = Math.max(1, maxDisplayFreq.value);
  const left = (freqRange.value[0] / total) * 100;
  const width = ((freqRange.value[1] - freqRange.value[0]) / total) * 100;
  return { left: `${left}%`, width: `${Math.max(0.5, width)}%` };
});

const hasSpectrumData = computed(() => {
  if (previewSpectrum.value.length > 1 || spectra.value.length > 0) return true;
  if (spectrogramRows.value.length > 0) return true;
  return Object.values(spectrogramRowsByChannel.value).some((rows) => rows.length > 0);
});

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const ensureChannelSchema = (count: number, names?: string[]) => {
  const normalizedCount = Math.max(1, Math.floor(Number(count) || 1));
  const normalizedNames = Array.from({ length: normalizedCount }, (_, i) => {
    return names?.[i] || channelNames.value[i] || `CH${i + 1}`;
  });
  channelCount.value = normalizedCount;
  channelNames.value = normalizedNames;
  selectedChannels.value = selectedChannels.value
    .map((ch) => clamp(Math.floor(ch), 0, normalizedCount - 1))
    .filter((ch, idx, arr) => arr.indexOf(ch) === idx);
  if (selectedChannels.value.length === 0) selectedChannels.value = [0];
};

const resetData = () => {
  backendSpectra.value = [];
  backendAverageSpectrum.value = [];
  spectrogramRows.value = [];
  spectrogramRowsByChannel.value = {};
  spectrogramPendingFrames.value = [];
  spectrogramScanPos.value = 0;
  spectrogramLayoutKey.value = '';
  spectra.value = [];
  previewSpectrum.value = [];
  packetCount.value = 0;
  bufferFill.value = 0;
  lastFramePos = null;
  lastDataTimestamp = 0;
  lastDataWallTime = 0;
};

const getActiveChannels = () => {
  const normalized = (selectedChannels.value.length > 0 ? selectedChannels.value : [0])
    .map((ch) => clamp(Math.floor(ch), 0, channelCount.value - 1))
    .filter((ch, idx, arr) => arr.indexOf(ch) === idx);
  return normalized.length > 0 ? normalized : [0];
};

const normalizeSpectrogramRow = (mags: number[], dbMin?: number, dbMax?: number) => {
  if (!Array.isArray(mags) || mags.length === 0) return [];
  const dbValues = mags.map((m) => 20 * Math.log10(Math.max(1e-9, Number(m) || 0)));
  let lo = Number.isFinite(dbMin) ? Number(dbMin) : Infinity;
  let hi = Number.isFinite(dbMax) ? Number(dbMax) : -Infinity;
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi <= lo) {
    for (const v of dbValues) {
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
  }
  const span = Math.max(1e-6, hi - lo);
  return dbValues.map((v) => clamp((v - lo) / span, 0, 1));
};

const makeSpectrogramLayout = () => {
  const { left, top, width: pW, height: pH } = plotMetrics.value;
  const channels = averageEnabled.value ? [-1] : getActiveChannels();
  const regionCount = Math.max(1, channels.length);
  const regionGap = 8;
  const totalGap = regionGap * (regionCount - 1);
  const usableWidth = Math.max(1, pW - totalGap);
  const dpr = Math.max(1, canvasSize.value.dpr || window.devicePixelRatio || 1);
  const topPx = Math.max(0, Math.floor(top * dpr));
  const heightPx = Math.max(1, Math.floor(Math.max(1, pH) * dpr));

  const regions = channels.map((ch, region) => {
    const regionLeft = left + ((usableWidth / regionCount) * region) + regionGap * region;
    const regionWidth = Math.max(1, usableWidth / regionCount);
    return {
      channel: ch,
      leftPx: Math.max(0, Math.floor(regionLeft * dpr)),
      widthPx: Math.max(1, Math.floor(regionWidth * dpr)),
    };
  });

  const key = `${channels.join(',')}|${regions.map((r) => `${r.leftPx}:${r.widthPx}`).join('|')}|${topPx}|${heightPx}|${freqRange.value.join(':')}`;
  return { regions, topPx, heightPx, key };
};

const clearSpectrogramCanvas = () => {
  if (spectrogramCtx) {
    spectrogramCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);
  }
  if (spectrogramOverlayCtx) {
    spectrogramOverlayCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);
  }
  lastFramePos = null;
  lastDataTimestamp = 0;
  lastDataWallTime = 0;
};

const resolveFrameRow = (frame: { avg?: number[]; channels: Record<number, number[]> }, channel: number) => {
  if (channel === -1) {
    if (frame.avg && frame.avg.length > 1) return frame.avg;
    const active = getActiveChannels();
    const rows = active
      .map((ch) => frame.channels[ch])
      .filter((row): row is number[] => Array.isArray(row) && row.length > 1);
    if (rows.length === 0) return [];
    const len = Math.min(...rows.map((r) => r.length));
    const avg = new Array(len).fill(0);
    for (let i = 0; i < len; i += 1) {
      for (const row of rows) avg[i] += row[i] || 0;
      avg[i] /= rows.length;
    }
    return avg;
  }
  return frame.channels[channel] || [];
};

const stepWindowSec = (step: number) => {
  const next = fftWindowSec.value + step;
  fftWindowSec.value = clamp(Math.round(next * 10) / 10, 0.1, 10);
};

const resetFreqRange = () => {
  freqRange.value = [0, maxDisplayFreq.value];
};

const onNodeSelected = (nodeId: string | null) => {
  if (!nodeId || nodeId === selectedNodeId.value) {
    settingsDialogOpen.value = false;
    return;
  }
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  selectedNodeId.value = nodeId;
  sessionStore.bindViewToNode(viewId, nodeId);

  const node = graphNodes.value.find((n) => n.id === nodeId);
  const paramNames = Array.isArray(node?.params?.availableChannels)
    ? (node?.params?.availableChannels as unknown[]).map((name, idx) => String(name || `CH${idx + 1}`))
    : null;
  if (paramNames && paramNames.length > 0) {
    ensureChannelSchema(paramNames.length, paramNames);
  }

  resetData();
  loadFreqSettings();
  if (isGraphFrozen.value) {
    eegWebSocket.subscribe([nodeId]);
  }
  settingsDialogOpen.value = false;
};

const unbindNode = () => {
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  selectedNodeId.value = null;
  sessionStore.bindViewToNode(viewId, null);
  resetData();
};

const openFullscreen = () => {
  if (!selectedNodeId.value) return;
  const routeData = router.resolve({
    name: 'Fullscreen',
    params: { type: 'freq', nodeId: selectedNodeId.value }
  });
  window.open(routeData.href, '_blank');
};

const updatePlotMetrics = () => {
  const { width, height } = canvasSize.value;
  plotMetrics.value.width = Math.max(0, width - plotMetrics.value.left - plotMetrics.value.right);
  plotMetrics.value.height = Math.max(0, height - plotMetrics.value.top - plotMetrics.value.bottom);
};

const drawGrid = () => {
  if (!gridCtx) return;
  const { width, height } = canvasSize.value;
  const { left, top, width: pW, height: pH } = plotMetrics.value;

  gridCtx.clearRect(0, 0, width, height);
  gridCtx.fillStyle = '#fff';
  gridCtx.fillRect(0, 0, width, height);

  gridCtx.strokeStyle = '#f1f1f1';
  gridCtx.lineWidth = 1;

  if (displayMode.value === 'spectrogram') {
    const yTicks = 8;
    const xTicks = 10;
    const channels = averageEnabled.value ? [-1] : getActiveChannels();
    const regionCount = Math.max(1, channels.length);
    const regionGap = 8;
    const totalGap = regionGap * (regionCount - 1);
    const usableWidth = Math.max(1, pW - totalGap);

    for (let i = 0; i <= yTicks; i += 1) {
      const y = top + (pH * i) / yTicks;
      gridCtx.beginPath();
      gridCtx.moveTo(left, y);
      gridCtx.lineTo(left + pW, y);
      gridCtx.stroke();
    }

    for (let region = 0; region < regionCount; region += 1) {
      const regionLeft = left + ((usableWidth / regionCount) * region) + regionGap * region;
      const regionWidth = usableWidth / regionCount;
      for (let i = 0; i <= xTicks; i += 1) {
        const x = regionLeft + (regionWidth * i) / xTicks;
        gridCtx.beginPath();
        gridCtx.moveTo(x, top);
        gridCtx.lineTo(x, top + pH);
        gridCtx.stroke();
      }
    }

    gridCtx.strokeStyle = '#e0e0e0';
    gridCtx.strokeRect(left, top, pW, pH);

    if (regionCount > 1) {
      gridCtx.strokeStyle = '#d7d7d7';
      for (let region = 1; region < regionCount; region += 1) {
        const dividerX = left + ((usableWidth / regionCount) * region) + regionGap * (region - 0.5);
        gridCtx.beginPath();
        gridCtx.moveTo(dividerX, top);
        gridCtx.lineTo(dividerX, top + pH);
        gridCtx.stroke();
      }
    }

    gridCtx.fillStyle = '#666';
    gridCtx.font = '10px sans-serif';
    gridCtx.textAlign = 'right';
    gridCtx.textBaseline = 'middle';
    const [fMin, fMax] = freqRange.value;
    for (let i = 0; i <= yTicks; i += 1) {
      const y = top + (pH * i) / yTicks;
      const hz = Math.round(fMax - ((fMax - fMin) * i) / yTicks);
      gridCtx.fillText(`${hz}`, left - 4, y);
    }

    gridCtx.textAlign = 'center';
    gridCtx.textBaseline = 'top';
    for (let region = 0; region < regionCount; region += 1) {
      const regionWidth = Math.max(1, usableWidth / regionCount);
      const regionLeft = left + (regionWidth * region) + regionGap * region;
      
      // 动态决定时间轴刻度密度，避免重叠
      const ticks = regionWidth > 200 ? [0, 0.2, 0.4, 0.6, 0.8, 1.0] : 
                    regionWidth > 120 ? [0, 0.5, 1.0] : [0, 1.0];

      for (const t of ticks) {
        const x = regionLeft + regionWidth * t;
        const sec = (t * spectrogramHistorySec.value).toFixed(1);
        gridCtx.fillText(sec, x, top + pH + 6);
      }

      const label = channels[region] === -1
        ? 'AVG'
        : (channelNames.value[channels[region]] || `CH${channels[region] + 1}`);
      gridCtx.textBaseline = 'bottom';
      gridCtx.fillStyle = '#555';
      gridCtx.fillText(label, regionLeft + regionWidth / 2, top - 2);
      gridCtx.textBaseline = 'top';
      gridCtx.fillStyle = '#666';
    }
    return;
  }

  for (let i = 0; i <= 5; i += 1) {
    const y = top + (pH * i) / 5;
    gridCtx.beginPath();
    gridCtx.moveTo(left, y);
    gridCtx.lineTo(left + pW, y);
    gridCtx.stroke();
  }

  for (let i = 0; i <= 10; i += 1) {
    const x = left + (pW * i) / 10;
    gridCtx.beginPath();
    gridCtx.moveTo(x, top);
    gridCtx.lineTo(x, top + pH);
    gridCtx.stroke();
  }

  gridCtx.strokeStyle = '#e0e0e0';
  gridCtx.strokeRect(left, top, pW, pH);

  const [fMin, fMax] = freqRange.value;
  gridCtx.fillStyle = '#666';
  gridCtx.font = '10px sans-serif';
  gridCtx.textAlign = 'center';
  gridCtx.textBaseline = 'top';
  for (let i = 0; i <= 10; i += 1) {
    const x = left + (pW * i) / 10;
    const hz = Math.round(fMin + ((fMax - fMin) * i) / 10);
    gridCtx.fillText(`${hz}`, x, top + pH + 6);
  }
};

const computeSpectra = () => {
  const source = backendSpectra.value;
  if (!source.length) {
    if (backendAverageSpectrum.value.length > 1) {
      spectra.value = [{ channel: -1, mags: backendAverageSpectrum.value, color: '#555' }];
      previewSpectrum.value = backendAverageSpectrum.value;
    } else {
      spectra.value = [];
      previewSpectrum.value = [];
    }
    return;
  }

  const channels = selectedChannels.value.length > 0 ? selectedChannels.value : [0];
  const computedSpectra: Array<{ channel: number; mags: number[]; color: string }> = [];

  for (const ch of channels) {
    const mags = source[ch] || [];
    if (mags.length === 0) continue;
    computedSpectra.push({ channel: ch, mags, color: channelColors[ch % channelColors.length] });
  }

  if (computedSpectra.length === 0) {
    spectra.value = [];
    previewSpectrum.value = [];
    return;
  }

  if (averageEnabled.value && computedSpectra.length > 1) {
    const len = Math.min(...computedSpectra.map((s) => s.mags.length));
    const avg = new Array(len).fill(0);
    for (let i = 0; i < len; i += 1) {
      for (const spec of computedSpectra) avg[i] += spec.mags[i];
      avg[i] /= computedSpectra.length;
    }
    computedSpectra.push({ channel: -1, mags: avg, color: '#555' });
    previewSpectrum.value = avg;
  } else {
    previewSpectrum.value = computedSpectra[0].mags;
  }

  spectra.value = computedSpectra;
};

const renderNow = () => {
  if (!canDisplay.value) return;
  if (displayMode.value === 'spectrogram') {
    drawSpectrogram();
  } else {
    drawSpectrum();
  }
  drawPreview();
};

const requestRender = () => {
  if (isRenderPending) return;
  isRenderPending = true;
  renderFrameId = requestAnimationFrame((ts) => {
    isRenderPending = false;
    if (!canDisplay.value) return;
    const elapsed = ts - lastRenderTime;
    if (elapsed < FRAME_INTERVAL) {
      requestRender();
      return;
    }
    lastRenderTime = ts;
    renderNow();
  });
};

const drawSpectrum = () => {
  if (!spectrumCtx) return;
  const { left, top, width: pW, height: pH } = plotMetrics.value;
  spectrumCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);
  if (spectra.value.length === 0) return;

  const [fMin, fMax] = freqRange.value;
  const span = Math.max(1, fMax - fMin);

  for (const spec of spectra.value) {
    if (spec.mags.length < 2) continue;
    const resolution = backendFreqResolution.value > 0
      ? backendFreqResolution.value
      : (sampleRate.value / Math.max(1, backendFftSize.value));
    const i0 = Math.max(0, Math.floor(fMin / resolution));
    const i1 = Math.min(spec.mags.length - 1, Math.ceil(fMax / resolution));
    if (i1 <= i0) continue;

    let maxMag = 0.0001;
    for (let i = i0; i <= i1; i += 1) {
      const m = spec.mags[i] || 0;
      if (m > maxMag) maxMag = m;
    }
    spectrumCtx.strokeStyle = spec.color;
    spectrumCtx.lineWidth = spec.channel === -1 ? 2.3 : 1.4;
    spectrumCtx.beginPath();

    for (let i = i0; i <= i1; i += 1) {
      const x = left + (((i * resolution) - fMin) / span) * pW;
      const y = top + pH - (spec.mags[i] / maxMag) * pH;
      if (i === i0) spectrumCtx.moveTo(x, y);
      else spectrumCtx.lineTo(x, y);
    }
    spectrumCtx.stroke();
  }
};

const hexToRgb = (hex: string) => {
  const normalized = hex.replace('#', '');
  const full = normalized.length === 3
    ? normalized.split('').map((c) => `${c}${c}`).join('')
    : normalized;
  const value = parseInt(full.substring(0, 6), 16);
  return {
    r: (value >> 16) & 0xff,
    g: (value >> 8) & 0xff,
    b: value & 0xff,
  };
};

const colorForValue = (v: number) => {
  const x = clamp(v, 0, 1);
  const n = heatmapPalette.length;
  if (n <= 1) return [0, 0, 0] as const;

  const scaled = x * (n - 1);
  const i0 = Math.floor(scaled);
  const i1 = Math.min(n - 1, i0 + 1);
  const t = scaled - i0;

  const c0 = hexToRgb(heatmapPalette[i0]);
  const c1 = hexToRgb(heatmapPalette[i1]);

  const r = Math.round(c0.r + (c1.r - c0.r) * t);
  const g = Math.round(c0.g + (c1.g - c0.g) * t);
  const b = Math.round(c0.b + (c1.b - c0.b) * t);
  return [r, g, b] as const;
};

const drawSpectrogram = () => {
  if (!spectrogramCtx) return;
  const { width: pH_dummy, height: pW_dummy } = plotMetrics.value; // Avoid naming collision if any
  const { width: pW, height: pH } = plotMetrics.value;
  if (pW <= 1 || pH <= 1) return;

  const layout = makeSpectrogramLayout();
  if (layout.key !== spectrogramLayoutKey.value) {
    spectrogramLayoutKey.value = layout.key;
    spectrogramScanPos.value = 0;
    clearSpectrogramCanvas();
  }

  const nowWall = performance.now();
  const windowTime = Math.max(0.1, spectrogramHistorySec.value);
  const regionWidthPx = layout.regions[0]?.widthPx || 1;
  const pixelsPerSecond = regionWidthPx / windowTime;

  // 1. 根据待处理帧进行绘制
  if (spectrogramPendingFrames.value.length > 0) {
    // 特殊处理积压包：优先绘制最新的数据
    if (spectrogramPendingFrames.value.length > 5) {
      spectrogramPendingFrames.value.splice(0, spectrogramPendingFrames.value.length - 2);
    }

    const maxColumnsPerFrame = 2;
    const framesToDraw = Math.min(maxColumnsPerFrame, spectrogramPendingFrames.value.length);

    for (let i = 0; i < framesToDraw; i += 1) {
      const frame = spectrogramPendingFrames.value.shift();
      if (!frame) break;

      const frameT = (frame.timestamp || Date.now()) / 1000;
      const currentPos = Math.floor((frameT % windowTime) * pixelsPerSecond);
      
      lastDataTimestamp = frame.timestamp || Date.now();
      lastDataWallTime = performance.now();

      const columnsToFill: number[] = [];
      if (lastFramePos === null) {
        columnsToFill.push(currentPos);
      } else {
        let pos = (lastFramePos + 1) % regionWidthPx;
        const steps = (currentPos >= lastFramePos) 
          ? (currentPos - lastFramePos) 
          : (regionWidthPx - lastFramePos + currentPos);
        
        const maxFill = Math.min(steps, regionWidthPx / 4);
        for (let s = 0; s < maxFill; s++) {
          columnsToFill.push((lastFramePos + 1 + s) % regionWidthPx);
        }
        if (maxFill < steps) {
          columnsToFill.push(currentPos);
        }
      }
      lastFramePos = currentPos;

      for (const region of layout.regions) {
        const row = resolveFrameRow(frame, region.channel);
        const bins = row.length;
        if (bins <= 1) continue;

        const resolution = backendFreqResolution.value || (sampleRate.value / (backendFftSize.value || 512));
        const [fViewMin, fViewMax] = freqRange.value;

        const image = spectrogramCtx.createImageData(1, layout.heightPx);
        for (let y = 0; y < layout.heightPx; y += 1) {
          const freqRatio = 1 - y / Math.max(1, layout.heightPx - 1);
          const f = fViewMin + freqRatio * (fViewMax - fViewMin);
          const bin = Math.min(bins - 1, Math.max(0, Math.round(f / resolution)));
          const value = row[bin] ?? 0;
          const [r, g, b] = colorForValue(value);
          const idx = y * 4;
          image.data[idx] = r;
          image.data[idx + 1] = g;
          image.data[idx + 2] = b;
          image.data[idx + 3] = 255;
        }

        for (const col of columnsToFill) {
          const xOffset = col % region.widthPx;
          const xPx = region.leftPx + xOffset;
          spectrogramCtx.putImageData(image, xPx, layout.topPx);
        }
      }
    }
  }

  // 2. 估计当前的扫描位置：基于最新的数据时间戳 + 此时流逝的现实时间
  if (lastDataTimestamp > 0) {
    const elapsedSec = (nowWall - lastDataWallTime) / 1000;
    const estimatedDataTime = (lastDataTimestamp / 1000) + elapsedSec;
    spectrogramScanPos.value = Math.floor((estimatedDataTime % windowTime) * pixelsPerSecond);
  } else {
    // 如果还没收到数据，扫描线停在初始位置或根据现实时间移动
    const now = Date.now() / 1000;
    spectrogramScanPos.value = Math.floor((now % windowTime) * pixelsPerSecond);
  }

  if (spectrogramOverlayCtx) {
    spectrogramOverlayCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);
    spectrogramOverlayCtx.save();
    spectrogramOverlayCtx.strokeStyle = 'rgba(255, 255, 255, 0.9)';
    spectrogramOverlayCtx.lineWidth = 1;
    for (const region of layout.regions) {
      const xOffset = spectrogramScanPos.value % Math.max(1, region.widthPx);
      const xPx = region.leftPx + xOffset;
      const x = xPx / Math.max(1, canvasSize.value.dpr || 1);
      const yTop = layout.topPx / Math.max(1, canvasSize.value.dpr || 1);
      const yBottom = (layout.topPx + layout.heightPx) / Math.max(1, canvasSize.value.dpr || 1);
      spectrogramOverlayCtx.beginPath();
      spectrogramOverlayCtx.moveTo(x + 0.5, yTop);
      spectrogramOverlayCtx.lineTo(x + 0.5, yBottom);
      spectrogramOverlayCtx.stroke();
    }
    spectrogramOverlayCtx.restore();
  }
};

const drawPreview = () => {
  if (!previewCanvasRef.value) return;
  if (!previewCtx) previewCtx = previewCanvasRef.value.getContext('2d');
  if (!previewCtx) return;

  const dpr = canvasSize.value.dpr || window.devicePixelRatio || 1;
  const w = previewCanvasRef.value.clientWidth;
  const h = previewCanvasRef.value.clientHeight;
  const rw = Math.max(1, Math.floor(w * dpr));
  const rh = Math.max(1, Math.floor(h * dpr));
  if (previewCanvasRef.value.width !== rw || previewCanvasRef.value.height !== rh) {
    previewCanvasRef.value.width = rw;
    previewCanvasRef.value.height = rh;
    previewCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  previewCtx.clearRect(0, 0, w, h);
  const mags = previewSpectrum.value;
  if (mags.length < 2) return;
  const maxMag = Math.max(...mags, 0.0001);

  previewCtx.strokeStyle = '#999';
  previewCtx.lineWidth = 1;
  previewCtx.beginPath();
  for (let i = 0; i < mags.length; i += 1) {
    const x = (i / (mags.length - 1)) * w;
    const y = h - (mags[i] / maxMag) * (h - 2);
    if (i === 0) previewCtx.moveTo(x, y);
    else previewCtx.lineTo(x, y);
  }
  previewCtx.stroke();
};

const initCanvas = () => {
  if (!chartContainerRef.value || !gridCanvasRef.value || !spectrumCanvasRef.value || !spectrogramCanvasRef.value || !spectrogramOverlayCanvasRef.value) return;
  gridCtx = gridCanvasRef.value.getContext('2d');
  spectrumCtx = spectrumCanvasRef.value.getContext('2d');
  spectrogramCtx = spectrogramCanvasRef.value.getContext('2d');
  spectrogramOverlayCtx = spectrogramOverlayCanvasRef.value.getContext('2d');
  previewCtx = previewCanvasRef.value?.getContext('2d') || null;

  const handleResize = () => {
    if (!chartContainerRef.value) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = chartContainerRef.value.getBoundingClientRect();
    canvasSize.value = { width: rect.width, height: rect.height, dpr };

    for (const canvas of [gridCanvasRef.value, spectrumCanvasRef.value, spectrogramCanvasRef.value, spectrogramOverlayCanvasRef.value]) {
      if (!canvas) continue;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      const ctx = canvas.getContext('2d');
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    if (previewCanvasRef.value && zoomOuterRef.value) {
      const zRect = zoomOuterRef.value.getBoundingClientRect();
      previewCanvasRef.value.width = Math.max(1, Math.floor(zRect.width * dpr));
      previewCanvasRef.value.height = Math.max(1, Math.floor(zRect.height * dpr));
      previewCanvasRef.value.style.width = `${zRect.width}px`;
      previewCanvasRef.value.style.height = `${zRect.height}px`;
      previewCtx = previewCanvasRef.value.getContext('2d');
      previewCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    updatePlotMetrics();
    drawGrid();
    requestRender();
  };

  resizeObserver?.disconnect();
  resizeObserver = new ResizeObserver(handleResize);
  resizeObserver.observe(chartContainerRef.value);
  if (zoomOuterRef.value) resizeObserver.observe(zoomOuterRef.value);
  handleResize();
};

const onGlobalMouseMove = (e: MouseEvent) => {
  if (!isDragging.value || !zoomOuterRef.value) return;
  const rect = zoomOuterRef.value.getBoundingClientRect();
  const dx = e.clientX - dragStartX;
  const totalFreq = Math.max(1, maxDisplayFreq.value);
  const dFreq = (dx / Math.max(1, rect.width)) * totalFreq;

  if (isDragging.value === 'box') {
    const width = initialFreqRange[1] - initialFreqRange[0];
    let min = initialFreqRange[0] + dFreq;
    let max = initialFreqRange[1] + dFreq;
    if (min < 0) {
      min = 0;
      max = width;
    }
    if (max > totalFreq) {
      max = totalFreq;
      min = totalFreq - width;
    }
    freqRange.value = [Math.round(min), Math.round(max)];
    return;
  }

  if (isDragging.value === 'left') {
    const next = clamp(initialFreqRange[0] + dFreq, 0, initialFreqRange[1] - 1);
    freqRange.value = [Math.round(next), initialFreqRange[1]];
    return;
  }

  const next = clamp(initialFreqRange[1] + dFreq, initialFreqRange[0] + 1, totalFreq);
  freqRange.value = [initialFreqRange[0], Math.round(next)];
};

const onGlobalMouseUp = () => {
  isDragging.value = null;
  document.removeEventListener('mousemove', onGlobalMouseMove);
  document.removeEventListener('mouseup', onGlobalMouseUp);
};

const onHandleMouseDown = (e: MouseEvent, side: 'left' | 'right') => {
  if (!canDisplay.value) return;
  isDragging.value = side;
  dragStartX = e.clientX;
  initialFreqRange = [...freqRange.value];
  document.addEventListener('mousemove', onGlobalMouseMove);
  document.addEventListener('mouseup', onGlobalMouseUp);
};

const onZoomMouseDown = (e: MouseEvent) => {
  if (!canDisplay.value) return;
  isDragging.value = 'box';
  dragStartX = e.clientX;
  initialFreqRange = [...freqRange.value];
  document.addEventListener('mousemove', onGlobalMouseMove);
  document.addEventListener('mouseup', onGlobalMouseUp);
};

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
  try {
    const packetNodeId = String(packet.nodeId);
    const selectedId = selectedNodeId.value ? String(selectedNodeId.value) : null;

    if (!selectedId || packetNodeId !== selectedId) {
      if (selectedId && packetNodeId && packetNodeId !== 'undefined' && selectedId !== 'undefined') {
        console.warn(`[FrequencyView] Mismatched packet nodeId="${packetNodeId}" vs selected="${selectedId}" — filtered out`);
      }
      return;
    }


  isGraphFrozen.value = true;

  const inferredCount = Math.max(
    Array.isArray(packet.channelNames) ? packet.channelNames.length : 0,
    Array.isArray(packet.spectra) ? packet.spectra.length : 0,
    Array.isArray(packet.channels) ? packet.channels.length : 0,
    1,
  );
  const inferredNames = Array.isArray(packet.channelNames)
    ? packet.channelNames.map((name, idx) => String(name || `CH${idx + 1}`))
    : undefined;
  ensureChannelSchema(inferredCount, inferredNames);

  const packetTs = Number(packet.utcFirstFrameMs || packet.timestamp || 0);
  if (Number.isFinite(packetTs) && packetTs > 0) {
    const lagMs = Date.now() - packetTs;
    if (lagMs > MAX_DISPLAY_LAG_MS) {
      spectrogramPendingFrames.value = [];
      // 不在此处 return — 频谱数据仍然可用，只是时频谱需丢弃积压帧
    } else {
      lastDataTimestamp = packetTs;
      lastDataWallTime = performance.now();
      processingDelayMs.value = lagMs;
      updateDelayHistory(lagMs);
    }
  } else {
    lastDataTimestamp = Date.now();
    lastDataWallTime = performance.now();
    processingDelayMs.value = 0;
  }

  if (packet.sampleRate && packet.sampleRate > 0 && packet.sampleRate !== sampleRate.value) {
    sampleRate.value = packet.sampleRate;
  }

  const frameSamples = packet.samples?.length || 1;
  bufferFill.value = Math.min(requiredSamples.value, bufferFill.value + frameSamples);

  if (packet.fftSize && packet.fftSize >= 8) {
    backendFftSize.value = packet.fftSize;
  }
  if (packet.freqResolution && packet.freqResolution > 0) {
    backendFreqResolution.value = packet.freqResolution;
  }

  if (Array.isArray(packet.spectra) && packet.spectra.length > 0) {
    backendSpectra.value = packet.spectra;
  }
  if (Array.isArray(packet.spectrum) && packet.spectrum.length > 1) {
    backendAverageSpectrum.value = packet.spectrum;
  }

  if (Array.isArray(packet.spectrogramRow) && packet.spectrogramRow.length > 1) {
    spectrogramRows.value.push(packet.spectrogramRow);
    const maxRows = Math.max(100, Math.round(spectrogramHistorySec.value * TARGET_FPS));
    if (spectrogramRows.value.length > maxRows) {
      spectrogramRows.value.splice(0, spectrogramRows.value.length - maxRows);
    }
  }

  if (Array.isArray(packet.spectra) && packet.spectra.length > 0) {
    const byChannel = { ...spectrogramRowsByChannel.value };
    const frame: { timestamp: number; avg?: number[]; channels: Record<number, number[]> } = { 
      timestamp: packet.utcFirstFrameMs || packet.timestamp || Date.now(),
      channels: {} 
    };
    if (Array.isArray(packet.spectrogramRow) && packet.spectrogramRow.length > 1) {
      frame.avg = packet.spectrogramRow;
    }
    const maxRows = Math.max(100, Math.round(spectrogramHistorySec.value * TARGET_FPS));
    for (let ch = 0; ch < Math.min(channelCount.value, packet.spectra.length); ch += 1) {
      const mags = packet.spectra[ch];
      if (!Array.isArray(mags) || mags.length <= 1) continue;
      const normalized = normalizeSpectrogramRow(mags, packet.spectrogramDbMin, packet.spectrogramDbMax);
      if (normalized.length <= 1) continue;
      const rows = byChannel[ch] ? [...byChannel[ch]] : [];
      rows.push(normalized);
      if (rows.length > maxRows) {
        rows.splice(0, rows.length - maxRows);
      }
      byChannel[ch] = rows;
      frame.channels[ch] = normalized;
    }
    spectrogramRowsByChannel.value = byChannel;

    if (Object.keys(frame.channels).length > 0 || (frame.avg && frame.avg.length > 1)) {
      spectrogramPendingFrames.value.push(frame);
      const maxPending = 5;
      if (spectrogramPendingFrames.value.length > maxPending) {
        spectrogramPendingFrames.value.splice(0, spectrogramPendingFrames.value.length - maxPending);
      }
    }
  }

  packetCount.value += 1;
  computeSpectra();
  requestRender();
  } catch (err) {
    console.error('[FrequencyView] Error in handleDataPacket:', err);
  }
};

// ========== localStorage 持久化 ==========
const FREQ_STORAGE_PREFIX = 'freq_settings_';

interface FreqSettings {
  fftWindowSec: number;
  freqRange: [number, number];
  selectedChannels: number[];
  averageEnabled: boolean;
  displayMode: 'spectrum' | 'spectrogram';
}

let _isLoadingFreqSettings = false;

const getFreqStorageKey = () => {
  const nodeId = selectedNodeId.value;
  return nodeId ? `${FREQ_STORAGE_PREFIX}${nodeId}` : `${FREQ_STORAGE_PREFIX}global`;
};

const loadFreqSettings = () => {
  try {
    _isLoadingFreqSettings = true;
    let key = getFreqStorageKey();
    let raw = localStorage.getItem(key);
    if (!raw && selectedNodeId.value) {
      raw = localStorage.getItem(`${FREQ_STORAGE_PREFIX}global`);
    }
    if (!raw) { _isLoadingFreqSettings = false; return; }
    const saved: Partial<FreqSettings> = JSON.parse(raw);
    if (typeof saved.fftWindowSec === 'number') {
      fftWindowSec.value = saved.fftWindowSec;
    }
    if (Array.isArray(saved.freqRange) && saved.freqRange.length === 2) {
      freqRange.value = [saved.freqRange[0], saved.freqRange[1]];
    }
    if (Array.isArray(saved.selectedChannels)) {
      selectedChannels.value = saved.selectedChannels;
    }
    if (typeof saved.averageEnabled === 'boolean') {
      averageEnabled.value = saved.averageEnabled;
    }
    if (saved.displayMode === 'spectrum' || saved.displayMode === 'spectrogram') {
      displayMode.value = saved.displayMode;
    }
    // 等待所有 watcher 同步执行完毕后再允许保存
    Promise.resolve().then(() => {
      _isLoadingFreqSettings = false;
    });
  } catch (e) {
    _isLoadingFreqSettings = false;
    console.warn('[FrequencyView] Failed to load settings:', e);
  }
};

let freqSaveTimer: ReturnType<typeof setTimeout> | null = null;
const saveFreqSettings = () => {
  if (_isLoadingFreqSettings) return;
  if (freqSaveTimer) clearTimeout(freqSaveTimer);
  freqSaveTimer = setTimeout(() => {
    try {
      const settings: FreqSettings = {
        fftWindowSec: fftWindowSec.value,
        freqRange: [...freqRange.value],
        selectedChannels: [...selectedChannels.value],
        averageEnabled: averageEnabled.value,
        displayMode: displayMode.value,
      };
      localStorage.setItem(getFreqStorageKey(), JSON.stringify(settings));
      if (selectedNodeId.value) {
        localStorage.setItem(`${FREQ_STORAGE_PREFIX}global`, JSON.stringify(settings));
      }
    } catch (e) {
      console.warn('[FrequencyView] Failed to save settings:', e);
    }
    freqSaveTimer = null;
  }, 300);
};

// 页面关闭前强制保存
const onBeforeUnload = () => {
  if (freqSaveTimer) {
    clearTimeout(freqSaveTimer);
    freqSaveTimer = null;
  }
  try {
    const settings: FreqSettings = {
      fftWindowSec: fftWindowSec.value,
      freqRange: [...freqRange.value],
      selectedChannels: [...selectedChannels.value],
      averageEnabled: averageEnabled.value,
      displayMode: displayMode.value,
    };
    localStorage.setItem(getFreqStorageKey(), JSON.stringify(settings));
    if (selectedNodeId.value) {
      localStorage.setItem(`${FREQ_STORAGE_PREFIX}global`, JSON.stringify(settings));
    }
  } catch {}
};

// ========== 图状态：通过 sessionStore 全局订阅 ==========
let unsubData: (() => void) | null = null;
let unsubStatus: (() => void) | null = null;
let unsubStore: (() => void) | null = null;

onMounted(async () => {
  // 从 localStorage 恢复设置
  loadFreqSettings();

  // 页面关闭前强制保存
  window.addEventListener('beforeunload', onBeforeUnload);

  sessionStore.bindViewToNode(viewId, selectedNodeId.value);
  initCanvas();

  // 从 sessionStore 获取初始图状态
  const graph = sessionStore.getGraph();
  graphNodes.value = graph.nodes || [];
  isGraphFrozen.value = graph.frozen || false;

  // 订阅 sessionStore 全局状态
  unsubStore = sessionStore.subscribe((state) => {
    graphNodes.value = state.graph.nodes || [];
    isGraphFrozen.value = state.graph.frozen || false;
  });

  unsubData = eegWebSocket.onData(handleDataPacket);
  unsubStatus = eegWebSocket.onStatusChange((status) => {
    wsStatus.value = status;
    if (status === 'connected' && isGraphFrozen.value && selectedNodeId.value) {
      eegWebSocket.subscribe([selectedNodeId.value]);
    }
  });

  if (eegWebSocket.isConnected() && isGraphFrozen.value && selectedNodeId.value) {
    eegWebSocket.subscribe([selectedNodeId.value]);
  }
  wsStatus.value = eegWebSocket.getStatus();
});

onUnmounted(() => {
  window.removeEventListener('beforeunload', onBeforeUnload);
  unsubStore?.();
  if (selectedNodeId.value) {
    eegWebSocket.unsubscribe([selectedNodeId.value]);
  }
  sessionStore.bindViewToNode(viewId, null);
  onGlobalMouseUp();
  unsubData?.();
  unsubStatus?.();
  resizeObserver?.disconnect();
  if (renderFrameId) {
    cancelAnimationFrame(renderFrameId);
    renderFrameId = 0;
  }
});

watch(selectedChannels, (channels) => {
  const normalized = channels
    .map((v) => clamp(Math.floor(v), 0, channelCount.value - 1))
    .filter((v, i, arr) => arr.indexOf(v) === i);
  if (normalized.length === 0) normalized.push(0);
  const same = normalized.length === channels.length && normalized.every((v, i) => v === channels[i]);
  if (!same) {
    selectedChannels.value = normalized;
    return;
  }
  saveFreqSettings();
  computeSpectra();
  drawGrid();
  requestRender();
}, { deep: true });

watch(averageEnabled, () => {
  saveFreqSettings();
  computeSpectra();
  drawGrid();
  requestRender();
});

watch([sampleRate, fftWindowSec], () => {
  spectrogramHistorySec.value = clamp(Math.round(fftWindowSec.value * 10) / 10, 1, 10);
  if (freqRange.value[1] > maxDisplayFreq.value) {
    freqRange.value = [0, maxDisplayFreq.value];
  }
  saveFreqSettings();
  computeSpectra();
  drawGrid();
  requestRender();
});

watch(freqRange, () => {
  saveFreqSettings();
  drawGrid();
  requestRender();
}, { deep: true });

watch(maxDisplayFreq, (limit) => {
  if (freqRange.value[1] > limit || freqRange.value[0] >= freqRange.value[1]) {
    freqRange.value = [0, limit];
  }
});

watch(canDisplay, (enabled) => {
  if (!enabled) return;
  requestAnimationFrame(() => {
    initCanvas();
    drawGrid();
    computeSpectra();
    requestRender();
  });
});

watch(displayMode, () => {
  if (displayMode.value === 'spectrum') {
    clearSpectrogramCanvas();
  } else if (spectrumCtx) {
    spectrumCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);
  }
  saveFreqSettings();
  drawGrid();
  requestRender();
});

watch(isGraphFrozen, (frozen) => {
  if (!selectedNodeId.value) return;
  if (frozen) eegWebSocket.subscribe([selectedNodeId.value]);
  else eegWebSocket.unsubscribe([selectedNodeId.value]);
});
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

.osc-status-label {
  font-size: 11px;
  color: #666;
  white-space: nowrap;
}

.osc-status-text {
  font-size: 11px;
  color: #444;
  white-space: nowrap;
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
  min-width: 40px;
  text-align: center;
  font-size: 11px;
  font-weight: 600;
  color: #444;
  padding: 0 4px;
}

.osc-select-source-alert {
  cursor: pointer;
  padding: 12px;
  border-radius: 8px;
}

.osc-select-source-link {
  text-decoration: underline;
  font-weight: 600;
  color: #1e88e5;
  margin-left: 4px;
}

.osc-chart-container {
  position: relative;
  height: 320px; /* Fixed height for card mode */
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

.osc-canvas-hidden {
  display: none;
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
  z-index: 10;
}

.freq-datazoom-wrap {
  border-top: 1px solid #f0f0f0;
  background-color: #f9f9f9;
}

.freq-datazoom-inner {
  position: relative;
  height: 40px;
  border: 1px solid #e0e0e0;
  background: #fff;
  cursor: crosshair;
}

.zoom-preview-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.zoom-selection-mask {
  position: absolute;
  top: 0;
  bottom: 0;
  background-color: rgba(135, 206, 235, 0.2);
  border: 1px solid rgba(135, 206, 235, 0.8);
  box-sizing: border-box;
  cursor: move;
  z-index: 2;
}

.zoom-handle {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 8px;
  background-color: #fff;
  border: 1px solid #999;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 3;
}

.zoom-handle.left {
  left: -4px;
  cursor: ew-resize;
  border-radius: 4px 0 0 4px;
}

.zoom-handle.right {
  right: -4px;
  cursor: ew-resize;
  border-radius: 0 4px 4px 0;
}

.handle-line {
  width: 1px;
  height: 12px;
  background-color: #999;
}

.gap-2 {
  gap: 8px;
}
</style>
