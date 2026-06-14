<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between pa-3">
      <div class="d-flex align-center">
        10-20 脑电可视化
        <v-tooltip location="bottom">
          <template #activator="{ props: toolProps }">
            <v-icon v-bind="toolProps" size="small" class="ml-2" color="info">mdi-information</v-icon>
          </template>
          <div>
            <div>数据源: {{ dataSourceText }}</div>
            <div v-if="targetNode">绑定节点: {{ targetNode.name }}</div>
            <div>已映射导联: {{ electrodeMap.size }} 个</div>
          </div>
        </v-tooltip>
      </div>

      <div class="d-flex align-center ga-2 flex-wrap">
        <!-- 10-20 通道配置开关 -->
        <v-btn
          size="small"
          variant="tonal"
          :color="hasElectrodeMap ? 'primary' : 'grey'"
          @click="channelDialogOpen = true"
        >
          <v-icon left size="small">mdi-map-marker</v-icon>
          {{ hasElectrodeMap ? `${electrodeMap.size}个导联` : '配置导联' }}
        </v-btn>

        <!-- 显示模式选择 -->
        <v-btn-toggle
          v-model="displayMode"
          mandatory
          density="compact"
          class="mr-1"
        >
          <v-btn value="topo" size="x-small" :disabled="!canDisplay">脑地形图</v-btn>
          <v-btn value="phase" size="x-small" :disabled="!canDisplay">锁相图</v-btn>
          <v-btn value="both" size="x-small" :disabled="!canDisplay">叠加</v-btn>
        </v-btn-toggle>

        <!-- 数据源选择 -->
        <v-select
          v-model="selectedNodeId"
          :items="availableSources"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          placeholder="选数据源"
          style="width: 140px"
          @update:model-value="onNodeSelected"
        />

        <!-- 颜色映射范围 -->
        <v-text-field
          v-if="displayMode !== 'phase'"
          v-model.number="colorRangeMax"
          type="number"
          label="幅值上限"
          density="compact"
          variant="outlined"
          hide-details
          style="width: 80px"
          :disabled="!canDisplay"
        />

        <v-chip size="small" :color="statusColor">
          <v-icon left size="x-small">{{ statusIcon }}</v-icon>
          {{ statusText }}
        </v-chip>

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

    <v-card-text class="pa-2">
      <!-- 未配置导联提示 -->
      <v-alert
        v-if="!hasElectrodeMap"
        type="info"
        variant="tonal"
        class="mb-3"
        density="compact"
      >
        请点击「配置导联」按钮将通道映射到 10-20 标准导联系统。
      </v-alert>

      <!-- 未选择数据源提示 -->
      <v-alert
        v-else-if="!selectedNodeId"
        type="info"
        variant="tonal"
        class="mb-3"
        density="compact"
      >
        请从上方下拉菜单选择数据源节点。
        <router-link to="/cpgraph" target="_blank">前往计算图编辑器 →</router-link>
      </v-alert>

      <!-- 计算图未冻结提示 -->
      <v-alert
        v-else-if="!isGraphFrozen"
        type="warning"
        variant="tonal"
        class="mb-3"
        density="compact"
      >
        计算图未冻结，请在<router-link to="/cpgraph" target="_blank">计算图编辑器</router-link>中冻结计算图。
      </v-alert>

      <!-- ECharts 可视化区域 -->
      <div class="topo-wrap">
        <div ref="chartContainer" class="topo-chart" :class="{ disabled: !canDisplay }"></div>

        <!-- 无数据遮罩 -->
        <div v-if="!canDisplay" class="no-data-overlay">
          <v-icon size="48" color="grey-lighten-1">mdi-brain</v-icon>
          <div class="text-h6 mt-2">{{ noDataText }}</div>
        </div>

        <div class="topo-footer">
          <div>采样率: {{ currentSampleRate }} Hz</div>
          <div>接收包数: {{ packetCount }}</div>
          <div v-if="displayMode === 'topo' || displayMode === 'both'">
            幅值范围: -{{ colorRangeMax }} ~ +{{ colorRangeMax }} μV
          </div>
          <div v-if="displayMode === 'phase' || displayMode === 'both'">
            锁相阈值: {{ phaseThreshold }}
          </div>
        </div>
      </div>
    </v-card-text>

    <!-- 10-20 导联配置对话框 -->
    <TenTwentyChannelDialog
      v-model="channelDialogOpen"
      :initial-subject-id="subjectId"
      :initial-mappings="currentMappings"
      :devices="availableDevicesForTenTwenty"
      @confirm="onChannelConfigConfirm"
    />
  </v-card>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from 'vue';
import * as echarts from 'echarts';
import { eegWebSocket, type EegDataPacket } from '../services/websocket';
import { fetchGraph, syncGraph } from '../services/graph';
import { sessionStore } from '../services/sessionStore';
import type { GraphNode } from '../services/graph';
import TenTwentyChannelDialog from './TenTwentyChannelDialog.vue';
import {
  getTenTwentyPositions,
  parseChannelName,
  type ElectrodePosition,
  type ElectrodeMapping,
  type TenTwentyDialogResult,
} from '../data/ten_twenty_positions';

const props = defineProps<{
  initialNodeId?: string;
}>();

const emit = defineEmits<{
  (e: 'remove'): void;
}>();

// ============ 配置 ============
const sampleRate = 1000;
const bufferSize = 256;  // FFT 窗口大小
const channelCount = 8;  // 硬件通道数

// ============ 状态 ============
const chartContainer = ref<HTMLElement | null>(null);
let chartInstance: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationId = 0;
let lastRenderTime = 0;
let unsubData: (() => void) | null = null;
let unsubStatus: (() => void) | null = null;

const displayMode = ref<'topo' | 'phase' | 'both'>('topo');
const colorRangeMax = ref(50); // μV

const selectedNodeId = ref<string | null>(props.initialNodeId || null);
const graphNodes = ref<GraphNode[]>([]);
const isGraphFrozen = ref(false);
const packetCount = ref(0);
const lastPacketTime = ref(0);
let graphStateTimer: ReturnType<typeof setInterval> | null = null;

const wsStatus = ref<'disconnected' | 'connecting' | 'connected' | 'error'>('disconnected');
const subjectId = ref('');
const electrodeMap = ref<Map<string, number>>(new Map()); // 10-20名称 → 通道索引
const electrodeMappings = ref<ElectrodeMapping[]>([]); // 详细映射信息
const channelDialogOpen = ref(false);

/** 转为 dialog 需要的 initialMappings 格式 */
const currentMappings = computed((): ElectrodeMapping[] => {
  return electrodeMappings.value;
});

/** 可用设备列表 */
const availableDevicesForTenTwenty = computed(() => {
  const devices = sessionStore.getDevices();
  return devices.map((d: any) => ({
    id: d.id,
    name: d.name,
    channelCount: d.channelCount,
    channels: (d.config?.channels || []).map((ch: any) => ({
      index: ch.index ?? ch.channel ?? 0,
      name: ch.name || `CH${(ch.index ?? 0) + 1}`,
      alias: ch.alias || '',
    })),
  }));
});

// 数据缓冲: 每个通道的 sample buffer
const sampleBuffers: number[][] = Array.from({ length: channelCount }, () => []);

// 最近一次的各通道功率谱
const lastSpectra = ref<Map<string, number[]>>(new Map()); // electrodeName → spectrum[]
// 最近一次的各通道相位谱
const lastPhaseSpectra = ref<Map<string, number[]>>(new Map());

// ============ 计算属性 ============
const hasElectrodeMap = computed(() => electrodeMap.value.size > 0);

const availableSources = computed(() =>
  graphNodes.value.filter((n) => n.type === 'OSC' || n.type === 'SPECTRUM')
);

const targetNode = computed(() => {
  if (!selectedNodeId.value) return null;
  return graphNodes.value.find((n) => n.id === selectedNodeId.value);
});

const canDisplay = computed(() =>
  hasElectrodeMap.value &&
  !!selectedNodeId.value &&
  isGraphFrozen.value &&
  wsStatus.value === 'connected'
);

const dataSourceText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  const node = targetNode.value;
  return node ? node.name : selectedNodeId.value;
});

const currentSampleRate = computed(() => sampleRate);

const noDataText = computed(() => {
  if (!hasElectrodeMap.value) return '请配置10-20导联映射';
  if (!selectedNodeId.value) return '请选择数据源';
  if (!isGraphFrozen.value) return '计算图未冻结';
  if (wsStatus.value !== 'connected') return '等待连接';
  return '等待数据';
});

const statusText = computed(() => {
  if (!selectedNodeId.value) return '未选择';
  if (!isGraphFrozen.value) return '未冻结';
  switch (wsStatus.value) {
    case 'connected': return packetCount.value > 0 ? '接收中' : '等待';
    case 'connecting': return '连接中';
    case 'error': return '错误';
    default: return '未连接';
  }
});

const statusColor = computed(() => {
  if (!selectedNodeId.value) return 'grey';
  if (!isGraphFrozen.value) return 'warning';
  switch (wsStatus.value) {
    case 'connected': return packetCount.value > 0 ? 'success' : 'info';
    case 'connecting': return 'info';
    case 'error': return 'error';
    default: return 'grey';
  }
});

const statusIcon = computed(() => {
  switch (statusColor.value) {
    case 'success': return 'mdi-check-circle';
    case 'warning': return 'mdi-alert';
    case 'error': return 'mdi-alert-circle';
    case 'info': return 'mdi-sync';
    default: return 'mdi-minus-circle';
  }
});

const phaseThreshold = ref(0.5); // 锁相阈值 (0-1)

// ============ 10-20 位置数据 ============
const allPositions = getTenTwentyPositions();

// ============ 插值算法 (Inverse Distance Weighting) ============

function idwInterpolate(
  gridX: number,
  gridY: number,
  electrodes: Array<{ x: number; y: number; value: number }>,
  power = 3,
): number {
  let numerator = 0;
  let denominator = 0;
  const minDist = 1e-6;

  for (const el of electrodes) {
    const dx = gridX - el.x;
    const dy = gridY - el.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist < minDist) return el.value;
    const w = 1 / Math.pow(dist, power);
    numerator += w * el.value;
    denominator += w;
  }
  return denominator > 0 ? numerator / denominator : 0;
}

/**
 * 生成插值网格用于渲染脑地形图
 */
function generateTopoGrid(
  electrodeValues: Map<string, number>,
  gridSize = 64,
): Array<{ x: number; y: number; value: number; inHead: boolean }> {
  const electrodes: Array<{ x: number; y: number; value: number }> = [];

  for (const [name, value] of electrodeValues.entries()) {
    const pos = allPositions.find((p) => p.name === name);
    if (pos) {
      electrodes.push({ x: pos.x, y: pos.y, value });
    }
  }

  if (electrodes.length === 0) return [];

  const headRadius = 1.0;
  const grid: Array<{ x: number; y: number; value: number; inHead: boolean }> = [];
  const step = (headRadius * 2.2) / gridSize;
  const offset = -headRadius * 1.1;

  for (let iy = 0; iy < gridSize; iy++) {
    for (let ix = 0; ix < gridSize; ix++) {
      const x = offset + ix * step;
      const y = offset + iy * step;
      const inHead = Math.sqrt(x * x + y * y) <= headRadius;
      const value = inHead ? idwInterpolate(x, y, electrodes) : 0;
      grid.push({ x, y, value, inHead });
    }
  }

  return grid;
}

// ============ FFT 计算 ============

function computeFFT(samples: number[]): { magnitude: number[]; phase: number[] } {
  const n = bufferSize;
  const real = [...samples.slice(0, n)];
  while (real.length < n) real.push(0);

  // 简单的 DFT (对于 256 点可以接受; 生产环境可用 FFT 库)
  const magnitude = new Array(n / 2).fill(0);
  const phase = new Array(n / 2).fill(0);

  for (let k = 0; k < n / 2; k++) {
    let reSum = 0;
    let imSum = 0;
    for (let j = 0; j < n; j++) {
      const angle = (-2 * Math.PI * k * j) / n;
      reSum += real[j] * Math.cos(angle);
      imSum += real[j] * Math.sin(angle);
    }
    magnitude[k] = Math.sqrt(reSum * reSum + imSum * imSum) / n * 2;
    phase[k] = Math.atan2(imSum, reSum);
  }

  return { magnitude, phase };
}

/**
 * 计算通道间的相位锁定值 (PLV)
 */
function computePLV(
  phaseSpectra: Map<string, number[]>,
  freqBinStart: number,
  freqBinEnd: number,
): Array<{ source: string; target: string; plv: number }> {
  const names = Array.from(phaseSpectra.keys());
  const links: Array<{ source: string; target: string; plv: number }> = [];

  for (let i = 0; i < names.length; i++) {
    for (let j = i + 1; j < names.length; j++) {
      const phaseI = phaseSpectra.get(names[i])!;
      const phaseJ = phaseSpectra.get(names[j])!;

      // 在频带内计算相位差的平均一致性
      let sumCos = 0;
      let sumSin = 0;
      let count = 0;
      for (let k = freqBinStart; k <= freqBinEnd && k < phaseI.length && k < phaseJ.length; k++) {
        const diff = phaseI[k] - phaseJ[k];
        sumCos += Math.cos(diff);
        sumSin += Math.sin(diff);
        count++;
      }
      if (count > 0) {
        const plv = Math.sqrt(sumCos * sumCos + sumSin * sumSin) / count;
        links.push({ source: names[i], target: names[j], plv });
      }
    }
  }

  return links;
}

// ============ ECharts 渲染 ============

function buildTopoChartOption(): echarts.EChartsOption {
  const electrodeValues = new Map<string, number>();
  const channels = Array.from(electrodeMap.value.entries());

  // 从 sample buffers 计算各通道当前 RMS
  for (const [elecName, chIdx] of channels) {
    const buf = sampleBuffers[chIdx];
    if (buf && buf.length > 0) {
      const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length);
      electrodeValues.set(elecName, rms);
    } else {
      electrodeValues.set(elecName, 0);
    }
  }

  const showTopo = displayMode.value === 'topo' || displayMode.value === 'both';
  const showPhase = displayMode.value === 'phase' || displayMode.value === 'both';

  const headRadius = 1.0;
  const series: echarts.SeriesOption[] = [];

  // ===== 头部轮廓 (custom) =====
  series.push({
    type: 'custom',
    name: 'head',
    z: 1,
    silent: true,
    renderItem: (_params: any, api: any) => {
      const cx = api.coord([0, 0])[0];
      const cy = api.coord([0, 0])[1];
      const r = api.size([headRadius, 0])[0];
      return {
        type: 'circle',
        shape: { cx, cy, r },
        style: { fill: '#ECEFF1', stroke: '#78909C', lineWidth: 2 },
      };
    },
  } as echarts.SeriesOption);

  // 鼻子
  series.push({
    type: 'custom',
    name: 'nose',
    z: 2,
    silent: true,
    renderItem: (_params: any, api: any) => {
      const cx = api.coord([0, 0])[0];
      const cy = api.coord([0, 0])[1];
      const headR = api.size([headRadius, 0])[0];
      const noseY = 0.12 * headR;
      const noseW = 0.06 * headR;
      return {
        type: 'polygon',
        shape: {
          points: [
            [cx, cy - headR],
            [cx + noseW, cy - headR - noseY * 0.8],
            [cx + noseW * 0.8, cy - headR - noseY],
            [cx - noseW * 0.8, cy - headR - noseY],
            [cx - noseW, cy - headR - noseY * 0.8],
          ],
        },
        style: { fill: '#B0BEC5', stroke: '#78909C', lineWidth: 1 },
      };
    },
  } as echarts.SeriesOption);

  // ===== 脑地形图 (插值热力图, 使用 scatter 渲染) =====
  if (showTopo && electrodeValues.size > 0) {
    const gridSize = 48;
    const topoGrid = generateTopoGrid(electrodeValues, gridSize);
    const maxVal = colorRangeMax.value;

    const topoData = topoGrid
      .filter((g) => g.inHead)
      .map((g) => {
        const normalizedVal = Math.max(-1, Math.min(1, g.value / Math.max(maxVal, 0.01)));
        return {
          value: [g.x, g.y, normalizedVal],
          symbolSize: Math.max(8, 100 / gridSize),
        };
      });

    series.push({
      type: 'scatter',
      name: 'topomap',
      z: 3,
      silent: true,
      data: topoData,
      symbolSize: (val: number[]) => val[2], // 使用 symbolSize 的第3维
      itemStyle: {
        color: (params: any) => {
          const v = params.value[2];
          // 蓝 (-) → 白 (0) → 红 (+)
          if (v < 0) {
            const t = Math.abs(v);
            const r = Math.round(30 + (1 - t) * 200);
            const g = Math.round(30 + (1 - t) * 200);
            const b = Math.round(255);
            return `rgb(${r},${g},${b})`;
          } else {
            const t = v;
            const r = Math.round(255);
            const g = Math.round(30 + (1 - t) * 200);
            const b = Math.round(30 + (1 - t) * 200);
            return `rgb(${r},${g},${b})`;
          }
        },
      },
      emphasis: { disabled: true },
    } as any);
  }

  // ===== 电极标记 =====
  const electrodeScatter = channels.map(([elecName]) => {
    const pos = allPositions.find((p) => p.name === elecName);
    return {
      name: elecName,
      value: pos ? [pos.x, pos.y] : [0, 0],
      symbolSize: 12,
    };
  });

  series.push({
    type: 'scatter',
    name: 'electrodes',
    z: 10,
    data: electrodeScatter,
    symbolSize: 12,
    itemStyle: {
      color: '#37474F',
      borderColor: '#ECEFF1',
      borderWidth: 2,
    },
    label: {
      show: true,
      position: 'bottom',
      distance: 6,
      fontSize: 10,
      color: '#455A64',
      fontWeight: 'bold',
    },
  } as echarts.SeriesOption);

  // ===== 锁相连接线 =====
  if (showPhase && electrodeValues.size >= 2) {
    // 计算各通道相位谱并计算 PLV
    const phaseMap = new Map<string, number[]>();

    for (const [elecName, chIdx] of channels) {
      const buf = sampleBuffers[chIdx];
      if (buf && buf.length >= bufferSize) {
        const { phase } = computeFFT(buf);
        phaseMap.set(elecName, phase);
      }
    }

    // 在 alpha 频段 (8-13 Hz) 计算 PLV
    const freqBinStart = Math.floor((8 / sampleRate) * bufferSize);
    const freqBinEnd = Math.floor((13 / sampleRate) * bufferSize);
    const plvLinks = computePLV(phaseMap, freqBinStart, freqBinEnd);

    const linesData = plvLinks
      .filter((l) => l.plv >= phaseThreshold.value)
      .map((l) => {
        const srcPos = allPositions.find((p) => p.name === l.source);
        const tgtPos = allPositions.find((p) => p.name === l.target);
        if (!srcPos || !tgtPos) return null;
        const alpha = Math.min(1, l.plv * 2); // 放大视觉差异
        return {
          coords: [[srcPos.x, srcPos.y], [tgtPos.x, tgtPos.y]],
          lineStyle: {
            color: `rgba(33, 150, 243, ${alpha})`,
            width: 1 + l.plv * 4,
          },
        };
      })
      .filter(Boolean);

    series.push({
      type: 'lines',
      name: 'plv_links',
      z: 5,
      coordinateSystem: 'cartesian2d',
      polyline: false,
      data: linesData as any,
      silent: true,
      lineStyle: { type: 'solid' },
    } as any);
  }

  // 颜色映射 colorbar (使用 graphic)
  const graphic: echarts.GraphicComponentOption[] = [];
  if (showTopo) {
    graphic.push({
      type: 'group',
      right: 10,
      top: 'center',
      children: [
        // 色条背景
        {
          type: 'rect',
          shape: { x: 0, y: -100, width: 16, height: 200 },
          style: { fill: 'transparent' },
        },
        // 使用多个小矩形模拟渐变色条
        ...Array.from({ length: 20 }, (_, i) => {
          const t = i / 19;
          const v = (1 - t) * 2 - 1; // 1 → -1
          const y = -100 + i * 10;
          let color: string;
          if (v < 0) {
            const a = Math.abs(v);
            color = `rgb(${Math.round(30 + (1 - a) * 200)},${Math.round(30 + (1 - a) * 200)},255)`;
          } else {
            color = `rgb(255,${Math.round(30 + (1 - v) * 200)},${Math.round(30 + (1 - v) * 200)})`;
          }
          return {
            type: 'rect',
            shape: { x: 0, y, width: 16, height: 10 },
            style: { fill: color },
          };
        }),
        {
          type: 'text',
          style: {
            text: `+${colorRangeMax.value}`,
            x: 8,
            y: -120,
            textAlign: 'center',
            fontSize: 10,
            fill: '#78909C',
          },
        },
        {
          type: 'text',
          style: {
            text: '0',
            x: 8,
            y: 0,
            textAlign: 'center',
            fontSize: 10,
            fill: '#78909C',
          },
        },
        {
          type: 'text',
          style: {
            text: `-${colorRangeMax.value}`,
            x: 8,
            y: 110,
            textAlign: 'center',
            fontSize: 10,
            fill: '#78909C',
          },
        },
        {
          type: 'text',
          style: {
            text: 'μV',
            x: 8,
            y: 130,
            textAlign: 'center',
            fontSize: 9,
            fill: '#90A4AE',
          },
        },
      ] as any,
    });
  }

  return {
    backgroundColor: 'transparent',
    graphic,
    grid: { left: 0, right: 60, top: 0, bottom: 0 },
    xAxis: {
      type: 'value',
      min: -1.25,
      max: 1.25,
      show: false,
    },
    yAxis: {
      type: 'value',
      min: -1.25,
      max: 1.25,
      show: false,
    },
    series,
  };
}

function initChart() {
  if (!chartContainer.value) return;
  if (chartInstance) {
    chartInstance.dispose();
  }
  chartInstance = echarts.init(chartContainer.value);
  chartInstance.setOption(buildTopoChartOption());
}

function renderLoop() {
  animationId = requestAnimationFrame(renderLoop);
  const now = Date.now();
  if (!canDisplay.value || now - lastRenderTime < 100) return; // 10fps
  lastRenderTime = now;

  if (chartInstance) {
    chartInstance.setOption(buildTopoChartOption(), true);
  }
};

function resizeChart() {
  const el = chartContainer.value;
  if (!el || !chartInstance) return;
  chartInstance.resize({ width: el.clientWidth, height: el.clientHeight });
}

// ============ WebSocket 数据接收 ============

function onDataPacket(packet: EegDataPacket) {
  if (!selectedNodeId.value) return;
  if (packet.nodeId !== selectedNodeId.value) return;

  packetCount.value++;
  lastPacketTime.value = Date.now();

  const chData = packet.channels || [];
  for (let i = 0; i < Math.min(chData.length, channelCount); i++) {
    const buf = sampleBuffers[i];
    if (!buf) continue;
    buf.push(chData[i]);
    if (buf.length > bufferSize * 2) {
      buf.splice(0, buf.length - bufferSize * 2);
    }
  }
}

// ============ 数据源管理 ============

function onNodeSelected(nodeId: string | null) {
  if (nodeId) {
    subscribeToNode(nodeId);
  }
}

function subscribeToNode(nodeId: string) {
  if (isGraphFrozen.value) {
    eegWebSocket.subscribe([nodeId]);
  }
}

// ============ 导联配置回调 ============

async function onChannelConfigConfirm(result: TenTwentyDialogResult) {
  subjectId.value = result.subjectId || '0';

  // 更新 electrodeMap: 电极名 → 通道索引
  const newMap = new Map<string, number>();
  for (const m of result.mappings) {
    newMap.set(m.electrode, m.channelIndex);
  }
  electrodeMap.value = newMap;

  // 保存完整映射信息
  electrodeMappings.value = [...result.mappings];

  // ===== 同步更新计算图节点的 channelNames =====
  if (!selectedNodeId.value) return;
  try {
    const targetNode = graphNodes.value.find(n => n.id === selectedNodeId.value);
    if (!targetNode) return;

    // 读取当前 channelNames，按映射重命名
    const currentNames: string[] = (targetNode.params?.channelNames as string[]) || [];
    const newNames = [...currentNames];
    // 确保长度足够
    for (const m of result.mappings) {
      while (newNames.length <= m.channelIndex) {
        newNames.push(`CH${newNames.length + 1}`);
      }
      newNames[m.channelIndex] = `${result.subjectId}@${m.electrode}`;
    }

    // 获取完整图、更新节点、同步
    const graph = await fetchGraph();
    const nodeToUpdate = graph.nodes?.find(n => n.id === selectedNodeId.value);
    if (nodeToUpdate) {
      nodeToUpdate.params = {
        ...nodeToUpdate.params,
        channelNames: newNames,
      };
      await syncGraph(graph);
      console.log('[TenTwentyTopoMap] Graph node channelNames updated:', newNames);
    }
  } catch (err) {
    console.error('[TenTwentyTopoMap] Failed to sync graph node channels:', err);
  }
}

// ============ 生命周期 ============

async function loadGraph() {
  try {
    const graph = await fetchGraph();
    graphNodes.value = graph.nodes || [];
    isGraphFrozen.value = graph.frozen ?? false;
  } catch (e) {
    console.error('[TenTwentyTopoMap] Failed to load graph:', e);
  }
}

onMounted(async () => {
  await loadGraph();

  // 定期刷新计算图状态
  graphStateTimer = setInterval(loadGraph, 3000);

  await nextTick();
  initChart();

  if (chartContainer.value) {
    resizeObserver = new ResizeObserver(() => resizeChart());
    resizeObserver.observe(chartContainer.value);
  }

  eegWebSocket.connect();

  unsubData = eegWebSocket.onData(onDataPacket);
  unsubStatus = eegWebSocket.onStatusChange((status) => {
    wsStatus.value = status;
  });

  // 如果有初始节点，订阅
  if (selectedNodeId.value && isGraphFrozen.value) {
    subscribeToNode(selectedNodeId.value);
  }

  // 启动渲染循环
  animationId = requestAnimationFrame(renderLoop);
});

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId);

  if (graphStateTimer) {
    clearInterval(graphStateTimer);
    graphStateTimer = null;
  }

  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }

  if (unsubData) { unsubData(); unsubData = null; }
  if (unsubStatus) { unsubStatus(); unsubStatus = null; }
  eegWebSocket.disconnect();

  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
});
</script>

<style scoped>
.topo-wrap {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  max-height: 500px;
  min-height: 300px;
}

.topo-chart {
  width: 100%;
  height: 100%;
}

.topo-chart.disabled {
  opacity: 0.3;
  pointer-events: none;
}

.no-data-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #9E9E9E;
  pointer-events: none;
}

.topo-footer {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #78909C;
  padding: 4px 8px;
}
</style>
