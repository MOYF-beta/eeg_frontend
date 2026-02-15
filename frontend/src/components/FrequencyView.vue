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
                  v-for="i in CHANNEL_COUNT"
                  :key="`channel-${i}`"
                  :value="i - 1"
                  size="small"
                >
                  CH{{ i }}
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
            <canvas ref="spectrumCanvasRef" class="osc-canvas" aria-hidden="true"></canvas>
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

        <div v-if="canDisplay && displayMode === 'spectrum'" class="freq-datazoom-wrap px-4 py-3">
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
import { eegWebSocket, type EegDataPacket } from '../services/websocket';
import { sessionStore } from '../services/sessionStore';
import { fetchGraph, type GraphNode } from '../services/graph';

defineEmits<{
  (e: 'remove'): void;
}>();

const props = defineProps<{
  initialNodeId?: string;
}>();

const CHANNEL_COUNT = 8;
const MAX_FREQ_LIMIT = 500;
const channelColors = ['#e53935', '#1e88e5', '#43a047', '#fdd835', '#8e24aa', '#fb8c00', '#00acc1', '#3949ab'];

const viewId = `freq-view-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;

const chartContainerRef = ref<HTMLDivElement | null>(null);
const gridCanvasRef = ref<HTMLCanvasElement | null>(null);
const spectrumCanvasRef = ref<HTMLCanvasElement | null>(null);
const previewCanvasRef = ref<HTMLCanvasElement | null>(null);
const zoomOuterRef = ref<HTMLDivElement | null>(null);

let gridCtx: CanvasRenderingContext2D | null = null;
let spectrumCtx: CanvasRenderingContext2D | null = null;
let previewCtx: CanvasRenderingContext2D | null = null;
let resizeObserver: ResizeObserver | null = null;
let renderFrameId = 0;

const TARGET_FPS = 24;
const FRAME_INTERVAL = 1000 / TARGET_FPS;
let lastRenderTime = 0;
let isRenderPending = false;

const settingsDialogOpen = ref(false);
const channelDialogOpen = ref(false);
const sampleRate = ref(1000);
const fftWindowSec = ref(1.0);
const freqRange = ref<[number, number]>([0, 125]);
const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');

const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);

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
const spectrogramHistorySec = ref(10);
const bufferFill = ref(0);

const canvasSize = ref({ width: 0, height: 0, dpr: 1 });
const plotMetrics = ref({ left: 46, right: 12, top: 12, bottom: 24, width: 0, height: 0 });

const isDragging = ref<'box' | 'left' | 'right' | null>(null);
let dragStartX = 0;
let initialFreqRange: [number, number] = [0, 0];

const requiredSamples = computed(() => Math.max(8, backendFftSize.value));
const maxDisplayFreq = computed(() => Math.min(MAX_FREQ_LIMIT, Math.floor(sampleRate.value / 2)));

const sampleCount = computed(() => bufferFill.value);

const availableOscNodes = computed(() => graphNodes.value.filter((n) => n.type === 'OSC' || n.type === 'SPECTRUM'));

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
  if (selectedChannels.value.length === 0) return 'CH1';
  return selectedChannels.value.map((ch) => `CH${ch + 1}`).join(', ');
});

const averageDisplayText = computed(() => `均值 ${selectedChannels.value.length} 通道`);

const selectionBoxStyle = computed(() => {
  const total = Math.max(1, maxDisplayFreq.value);
  const left = (freqRange.value[0] / total) * 100;
  const width = ((freqRange.value[1] - freqRange.value[0]) / total) * 100;
  return { left: `${left}%`, width: `${Math.max(0.5, width)}%` };
});

const hasSpectrumData = computed(() => previewSpectrum.value.length > 1 || spectra.value.length > 0);

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const resetData = () => {
  backendSpectra.value = [];
  backendAverageSpectrum.value = [];
  spectrogramRows.value = [];
  spectra.value = [];
  previewSpectrum.value = [];
  packetCount.value = 0;
  bufferFill.value = 0;
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
  resetData();
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

    for (let i = 0; i <= yTicks; i += 1) {
      const y = top + (pH * i) / yTicks;
      gridCtx.beginPath();
      gridCtx.moveTo(left, y);
      gridCtx.lineTo(left + pW, y);
      gridCtx.stroke();
    }

    for (let i = 0; i <= xTicks; i += 1) {
      const x = left + (pW * i) / xTicks;
      gridCtx.beginPath();
      gridCtx.moveTo(x, top);
      gridCtx.lineTo(x, top + pH);
      gridCtx.stroke();
    }

    gridCtx.strokeStyle = '#e0e0e0';
    gridCtx.strokeRect(left, top, pW, pH);

    gridCtx.fillStyle = '#666';
    gridCtx.font = '10px sans-serif';
    gridCtx.textAlign = 'right';
    gridCtx.textBaseline = 'middle';
    for (let i = 0; i <= yTicks; i += 1) {
      const y = top + (pH * i) / yTicks;
      const hz = Math.round(maxDisplayFreq.value * (1 - i / yTicks));
      gridCtx.fillText(`${hz}`, left - 4, y);
    }

    gridCtx.textAlign = 'center';
    gridCtx.textBaseline = 'top';
    for (let i = 0; i <= xTicks; i += 1) {
      const x = left + (pW * i) / xTicks;
      const sec = ((i / xTicks) * spectrogramHistorySec.value).toFixed(1);
      gridCtx.fillText(sec, x, top + pH + 6);
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
    return;
  }
  drawSpectrum();
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

const colorForValue = (v: number) => {
  const x = clamp(v, 0, 1);
  const r = Math.round(255 * clamp(1.5 - Math.abs(4 * x - 3), 0, 1));
  const g = Math.round(255 * clamp(1.5 - Math.abs(4 * x - 2), 0, 1));
  const b = Math.round(255 * clamp(1.5 - Math.abs(4 * x - 1), 0, 1));
  return [r, g, b] as const;
};

const drawSpectrogram = () => {
  if (!spectrumCtx) return;
  const { left, top, width: pW, height: pH } = plotMetrics.value;
  spectrumCtx.clearRect(0, 0, canvasSize.value.width, canvasSize.value.height);

  const rows = spectrogramRows.value;
  if (rows.length === 0 || pW <= 1 || pH <= 1) return;

  const cols = Math.max(1, Math.floor(pW));
  const start = Math.max(0, rows.length - cols);
  const visibleRows = rows.slice(start);
  const bins = visibleRows[0]?.length || 0;
  if (bins <= 1) return;

  const image = spectrumCtx.createImageData(visibleRows.length, Math.max(1, Math.floor(pH)));
  const h = Math.max(1, Math.floor(pH));

  for (let x = 0; x < visibleRows.length; x += 1) {
    const row = visibleRows[x] || [];
    for (let y = 0; y < h; y += 1) {
      const freqRatio = 1 - y / Math.max(1, h - 1);
      const bin = Math.min(bins - 1, Math.max(0, Math.round(freqRatio * (bins - 1))));
      const value = row[bin] ?? 0;
      const [r, g, b] = colorForValue(value);
      const idx = (y * visibleRows.length + x) * 4;
      image.data[idx] = r;
      image.data[idx + 1] = g;
      image.data[idx + 2] = b;
      image.data[idx + 3] = 255;
    }
  }

  spectrumCtx.putImageData(image, left, top);
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
  if (!chartContainerRef.value || !gridCanvasRef.value || !spectrumCanvasRef.value) return;
  gridCtx = gridCanvasRef.value.getContext('2d');
  spectrumCtx = spectrumCanvasRef.value.getContext('2d');
  previewCtx = previewCanvasRef.value?.getContext('2d') || null;

  const handleResize = () => {
    if (!chartContainerRef.value) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = chartContainerRef.value.getBoundingClientRect();
    canvasSize.value = { width: rect.width, height: rect.height, dpr };

    for (const canvas of [gridCanvasRef.value, spectrumCanvasRef.value]) {
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
  if (!canDisplay.value || displayMode.value !== 'spectrum') return;
  isDragging.value = side;
  dragStartX = e.clientX;
  initialFreqRange = [...freqRange.value];
  document.addEventListener('mousemove', onGlobalMouseMove);
  document.addEventListener('mouseup', onGlobalMouseUp);
};

const onZoomMouseDown = (e: MouseEvent) => {
  if (!canDisplay.value || displayMode.value !== 'spectrum') return;
  isDragging.value = 'box';
  dragStartX = e.clientX;
  initialFreqRange = [...freqRange.value];
  document.addEventListener('mousemove', onGlobalMouseMove);
  document.addEventListener('mouseup', onGlobalMouseUp);
};

const handleDataPacket = (packet: EegDataPacket) => {
  if (!selectedNodeId.value || String(packet.nodeId) !== String(selectedNodeId.value)) return;

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

  packetCount.value += 1;
  computeSpectra();
  requestRender();
};

const updateGraphState = async () => {
  try {
    const graph = await fetchGraph();
    graphNodes.value = graph.nodes || [];
    isGraphFrozen.value = Boolean(graph.frozen);
    if (isGraphFrozen.value && selectedNodeId.value) {
      eegWebSocket.subscribe([selectedNodeId.value]);
    }
  } catch (error) {
    console.error('Failed to fetch graph state', error);
  }
};

let unsubData: (() => void) | null = null;
let unsubStatus: (() => void) | null = null;

onMounted(async () => {
  sessionStore.bindViewToNode(viewId, selectedNodeId.value);
  eegWebSocket.connect();
  initCanvas();
  await updateGraphState();

  unsubData = eegWebSocket.onData(handleDataPacket);
  unsubStatus = eegWebSocket.onStatusChange((status) => {
    wsStatus.value = status;
  });
  wsStatus.value = eegWebSocket.getStatus();
});

onUnmounted(() => {
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
    .map((v) => clamp(Math.floor(v), 0, CHANNEL_COUNT - 1))
    .filter((v, i, arr) => arr.indexOf(v) === i);
  if (normalized.length === 0) normalized.push(0);
  const same = normalized.length === channels.length && normalized.every((v, i) => v === channels[i]);
  if (!same) {
    selectedChannels.value = normalized;
    return;
  }
  computeSpectra();
  requestRender();
}, { deep: true });

watch([sampleRate, fftWindowSec], () => {
  spectrogramHistorySec.value = clamp(Math.round(fftWindowSec.value * 10) / 10, 1, 10);
  if (freqRange.value[1] > maxDisplayFreq.value) {
    freqRange.value = [0, maxDisplayFreq.value];
  }
  computeSpectra();
  drawGrid();
  requestRender();
});

watch(freqRange, () => {
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
  height: 320px;
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
