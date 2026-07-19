<template>
  <v-bottom-navigation
    v-if="visible"
    density="compact"
    height="32"
    class="status-bar"
    color="primary"
  >
    <!-- 管道延迟 -->
    <div class="status-section">
      <span class="status-label">管道</span>
      <span class="status-value" :style="{ color: pipelineColor }">{{ pipelineValue }}</span>
      <span class="status-unit">{{ pipelineUnit }}</span>
    </div>

    <v-divider vertical class="mx-1" />

    <!-- 各阶段耗时 -->
    <div class="status-section">
      <span class="status-label">源</span>
      <span class="status-value">{{ pipelineSource }}</span>
    </div>
    <div class="status-section">
      <span class="status-label">节点</span>
      <span class="status-value">{{ pipelineNode }}</span>
    </div>
    <div class="status-section">
      <span class="status-label">WS</span>
      <span class="status-value">{{ pipelineWs }}</span>
    </div>

    <v-divider vertical class="mx-1" />

    <!-- 吞吐量 -->
    <div class="status-section">
      <span class="status-label">吞吐</span>
      <span class="status-value">{{ samplesPerSec }}</span>
      <span class="status-unit">/s</span>
    </div>

    <v-divider vertical class="mx-1" />

    <!-- CPU -->
    <div class="status-section">
      <span class="status-label">CPU</span>
      <span class="status-value" :style="{ color: cpuColor }">{{ cpuPercent }}%</span>
    </div>

    <!-- 内存 -->
    <div class="status-section">
      <span class="status-label">RAM</span>
      <span class="status-value" :style="{ color: memColor }">{{ memUsedMb }}M</span>
      <span class="status-unit">/{{ memTotalMb }}M</span>
    </div>

    <v-divider vertical class="mx-1" />

    <!-- 磁盘 -->
    <div class="status-section">
      <span class="status-label">磁盘</span>
      <span class="status-value" :style="{ color: diskColor }">{{ diskPercent }}%</span>
      <span class="status-unit">{{ diskUsedGb }}/{{ diskTotalGb }}G</span>
    </div>

    <!-- 线程数 -->
    <div class="status-section">
      <span class="status-label">线程</span>
      <span class="status-value">{{ threadCount }}</span>
    </div>

    <v-divider vertical class="mx-1" />

    <div class="status-section">
      <span class="status-label">进程</span>
      <span class="status-value">{{ processMemMb }}M</span>
    </div>

    <v-divider vertical class="mx-1" />

    <!-- 录制状态 -->
    <div v-if="recordingActive" class="status-section" data-testid="statusbar-recording">
      <v-icon size="x-small" color="error" class="mr-1 recording-dot">mdi-record-circle</v-icon>
      <span class="status-value text-error">{{ recordingDurationText }}</span>
      <span class="status-unit recording-file" :title="recordingFilepath">{{ recordingFilename }}</span>
    </div>

    <div class="status-section">
      <v-icon size="x-small" :color="graphRunning ? 'success' : 'grey'" class="mr-1">mdi-graph-outline</v-icon>
      <span class="status-value" :style="{ color: graphProcDelay > 10000 ? '#E53935' : undefined }">{{ procDelayText }}</span>
    </div>

    <!-- WS 连接状态 -->
    <div class="status-section ml-auto">
      <v-icon
        size="x-small"
        :color="wsStatus === 'connected' ? 'success' : wsStatus === 'connecting' ? 'warning' : 'error'"
        class="mr-1"
      >mdi-circle</v-icon>
      <span class="status-value text-caption">{{ wsStatusText }}</span>
    </div>

    <!-- 轮询错误指示 -->
    <div v-if="pollError !== null" class="status-section">
      <v-icon size="x-small" color="error" class="mr-1">mdi-alert</v-icon>
      <span class="status-value text-caption text-error">错误</span>
    </div>
  </v-bottom-navigation>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { eegWebSocket } from '../services/websocket';
import { controlWebSocket } from '../services/controlWebSocket';
import { recordingStore } from '../services/recordingStore';
import { formatRecordingDuration } from '../services/uiLogic';

interface PipelineAvg {
  sourceGenUs: number;
  nodeComputeUs: number;
  wsSendUs: number;
  totalUs: number;
}

interface StatusData {
  pipeline: {
    latest: PipelineAvg;
    average: PipelineAvg;
    samplesPerSecond: number;
    totalSamples: number;
  };
  system: {
    cpuPercent?: number;
    memoryUsedMb?: number;
    memoryTotalMb?: number;
    memoryPercent?: number;
    diskUsedGb?: number;
    diskTotalGb?: number;
    diskPercent?: number;
    processMemoryMb?: number;
    threadCount?: number;
  };
}

const visible = ref(true);
const pollError = ref<string | null>(null);

// 控制 WS 订阅句柄
let unsubState: (() => void) | null = null;
// 性能数据仍需 HTTP 轮询（控制 WS 心跳间隔 30s，性能数据实时性要求更高）
let perfTimer: number | null = null;

const pipelineSource = ref('0');
const pipelineNode = ref('0');
const pipelineWs = ref('0');
const pipelineValue = ref('0');
const pipelineUnit = ref('µs');
const samplesPerSec = ref('0');
const cpuPercent = ref('0');
const memUsedMb = ref('0');
const memTotalMb = ref('0');
const diskPercent = ref('0');
const diskUsedGb = ref('0');
const diskTotalGb = ref('0');
const threadCount = ref('0');
const processMemMb = ref('0');
const graphRunning = ref(false);
const graphProcDelay = ref(0);

// 录制状态（全局 recordingStore 轮询）
let unsubRecording: (() => void) | null = null;
const recordingActive = computed(() => recordingStore.state.recording);
const recordingDurationText = computed(() => {
  const recs = recordingStore.state.recordings;
  if (recs.length === 0) return '';
  const secs = Math.max(...recs.map((r) => Number(r.duration) || 0));
  return formatRecordingDuration(secs);
});
const recordingFilename = computed(() => {
  const recs = recordingStore.state.recordings;
  if (recs.length === 0) return '';
  const fp = String(recs[0].filepath || '');
  const name = fp.split(/[\\/]/).pop() || fp;
  return recs.length > 1 ? `${name} +${recs.length - 1}` : name;
});
const recordingFilepath = computed(() =>
  recordingStore.state.recordings.map((r) => r.filepath).join('\n')
);

const procDelayText = computed(() => {
  const ms = graphProcDelay.value;
  if (ms <= 0) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
});

const wsStatus = computed(() => eegWebSocket.getStatus());
const wsStatusText = computed(() => {
  const s = wsStatus.value;
  if (s === 'connected') return '已连接';
  if (s === 'connecting') return '连接中';
  if (s === 'error') return '错误';
  return '断开';
});

const pipelineColor = computed(() => {
  const v = parseInt(pipelineValue.value, 10);
  if (Number.isNaN(v)) return undefined;
  const unit = pipelineUnit.value;
  const us = unit === 'ms' ? v * 1000 : unit === 's' ? v * 1000000 : v;
  if (us > 50000) return '#E53935';
  if (us > 10000) return '#FB8C00';
  return undefined;
});

const cpuColor = computed(() => {
  const v = parseFloat(cpuPercent.value);
  if (Number.isNaN(v)) return undefined;
  if (v > 80) return '#E53935';
  if (v > 50) return '#FB8C00';
  return undefined;
});

const memColor = computed(() => {
  const v = parseFloat(memUsedMb.value) / Math.max(1, parseFloat(memTotalMb.value));
  if (Number.isNaN(v)) return undefined;
  if (v > 0.9) return '#E53935';
  if (v > 0.7) return '#FB8C00';
  return undefined;
});

const diskColor = computed(() => {
  const v = parseFloat(diskPercent.value);
  if (Number.isNaN(v)) return undefined;
  if (v > 90) return '#E53935';
  if (v > 75) return '#FB8C00';
  return undefined;
});

async function pollStatus() {
  try {
    const res = await fetch('/api/status/');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: StatusData = await res.json();

    const avg = data.pipeline.average;
    if (avg) {
      const src = formatUs(avg.sourceGenUs);
      pipelineSource.value = `${src.value}${src.unit}`;
      const node = formatUs(avg.nodeComputeUs);
      pipelineNode.value = `${node.value}${node.unit}`;
      const ws = formatUs(avg.wsSendUs);
      pipelineWs.value = `${ws.value}${ws.unit}`;
      const total = formatUs(avg.totalUs);
      pipelineValue.value = total.value;
      pipelineUnit.value = total.unit;
    }

    samplesPerSec.value = String(data.pipeline.samplesPerSecond || '0');

    const sys = data.system;
    if (sys) {
      cpuPercent.value = String(sys.cpuPercent ?? '—');
      memUsedMb.value = String(sys.memoryUsedMb ?? '—');
      memTotalMb.value = String(sys.memoryTotalMb ?? '—');
      diskPercent.value = String(sys.diskPercent ?? '—');
      diskUsedGb.value = String(sys.diskUsedGb ?? '—');
      diskTotalGb.value = String(sys.diskTotalGb ?? '—');
      threadCount.value = String(sys.threadCount ?? '—');
      processMemMb.value = String(sys.processMemoryMb ?? '—');
    }

    // 图运行状态由控制 WS 推送，此处不再从 HTTP 读取

    pollError.value = null;
  } catch (err) {
    pollError.value = (err as Error).message;
    console.warn('[StatusBar] Poll failed:', err);
  }
}

function formatUs(us: number): { value: string; unit: string } {
  if (us > 1000000) return { value: (us / 1000000).toFixed(1), unit: 's' };
  if (us > 10000) return { value: (us / 1000).toFixed(1), unit: 'ms' };
  if (us <= 0) return { value: '0', unit: 'µs' };
  return { value: String(us), unit: 'µs' };
}

onMounted(() => {
  unsubRecording = recordingStore.subscribe();

  // 运行时状态通过控制 WS 订阅（替代轮询 graph/run/）
  unsubState = controlWebSocket.onState((cs) => {
    const rt = cs.runtime;
    graphRunning.value = Boolean(rt.running);
    graphProcDelay.value = Number(rt.processingDelayMs || 0);
  });

  // 性能指标仍需较高频率更新，保留 HTTP 轮询但仅取 pipeline+system 数据
  pollStatus();
  perfTimer = window.setInterval(pollStatus, 3000);
});

onUnmounted(() => {
  unsubRecording?.();
  if (unsubState) {
    unsubState();
    unsubState = null;
  }
  if (perfTimer) {
    clearInterval(perfTimer);
    perfTimer = null;
  }
});
</script>

<style scoped>
.status-bar {
  flex: none;
  height: 32px !important;
  border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  background: rgb(var(--v-theme-surface));
  display: flex;
  align-items: center;
  padding: 0 8px;
  gap: 2px;
  overflow: hidden;
  justify-content: flex-start;
}

.status-section {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  white-space: nowrap;
  font-size: 11px;
  line-height: 1;
}

.status-label {
  color: rgba(var(--v-theme-on-surface), 0.45);
  font-weight: 500;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.status-value {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
}

.status-unit {
  color: rgba(var(--v-theme-on-surface), 0.35);
  font-size: 10px;
}

.recording-file {
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.recording-dot {
  animation: recording-blink 1.6s ease-in-out infinite;
}

@keyframes recording-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.v-divider {
  height: 16px;
}

.ml-auto {
  margin-left: auto;
}
</style>
