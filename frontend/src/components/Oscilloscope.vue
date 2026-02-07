<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      波形可视化（基础版）
      <v-chip size="small" :color="statusColor">{{ statusText }}</v-chip>
    </v-card-title>
    <v-divider />
    <v-card-text>
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
            />
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
import { createEegSocket, type EegPacket } from '../services/ws';

const channelCount = 8;
const rowHeight = 90;
const channelScales = ref<number[]>(Array.from({ length: channelCount }, () => 1));
const timeWindowSec = ref(5);
const mode = ref<'scan' | 'scroll'>('scroll');
const modeItems = [
  { title: '扫描', value: 'scan' },
  { title: '滚动', value: 'scroll' },
];
const samples: Array<Array<{ t: number; v: number }>> = Array.from(
  { length: channelCount },
  () => [],
);
const canvasRef = ref<HTMLCanvasElement | null>(null);
const status = ref<'open' | 'close' | 'error'>('close');
let ws: WebSocket | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationId = 0;
let sweepStart = 0;
const lastPacketTime = ref<number>(0);

const statusText = computed(() => {
  if (status.value === 'open') return '在线';
  if (status.value === 'error') return '错误';
  return '离线';
});

const statusColor = computed(() => {
  if (status.value === 'open') return 'green';
  if (status.value === 'error') return 'red';
  return 'grey';
});

onMounted(() => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.hostname || 'localhost';
  const url = `${protocol}://${host}:8000/ws/stream/`;
  ws = createEegSocket(
    url,
    (packet: EegPacket) => {
      const t = typeof packet.t === 'number' ? packet.t : Date.now() / 1000;
      lastPacketTime.value = t;
      if (sweepStart === 0) sweepStart = t;
      packet.channels.slice(0, channelCount).forEach((v, idx) => {
        samples[idx].push({ t, v });
      });
      pruneSamples(t);
    },
    (s) => (status.value = s),
  );

  resizeObserver = new ResizeObserver(() => resizeCanvas());
  if (canvasRef.value) {
    resizeObserver.observe(canvasRef.value);
    resizeCanvas();
  }
  animationId = requestAnimationFrame(drawLoop);
});

onUnmounted(() => {
  ws?.close();
  if (resizeObserver && canvasRef.value) resizeObserver.unobserve(canvasRef.value);
  if (animationId) cancelAnimationFrame(animationId);
});

watch([timeWindowSec, mode], () => {
  if (lastPacketTime.value) sweepStart = lastPacketTime.value;
  pruneSamples(lastPacketTime.value || Date.now() / 1000);
});

const pruneSamples = (now: number) => {
  const cutoff = now - timeWindowSec.value;
  samples.forEach((ch) => {
    while (ch.length && ch[0].t < cutoff) ch.shift();
  });
};

const resizeCanvas = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 600;
  const height = rowHeight * channelCount;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  const ctx = canvas.getContext('2d');
  if (ctx) ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
};

const drawLoop = () => {
  drawWaveform();
  animationId = requestAnimationFrame(drawLoop);
};

const drawWaveform = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const width = canvas.clientWidth || 600;
  const height = rowHeight * channelCount;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= channelCount; i += 1) {
    const y = i * rowHeight;
    ctx.beginPath();
    ctx.moveTo(0, y);
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

    ctx.strokeStyle = '#1976d2';
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    let prevX = -1;
    ch.forEach((p) => {
      let x = 0;
      if (mode.value === 'scroll') {
        x = ((p.t - (now - timeWindow)) / timeWindow) * width;
        if (x < 0 || x > width) return;
      } else {
        const offset = (p.t - sweepStart) % timeWindow;
        x = (offset / timeWindow) * width;
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

    ctx.strokeStyle = '#bdbdbd';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(width, midY);
    ctx.stroke();
    ctx.setLineDash([]);
  });
};
</script>

<style scoped>
.osc-root {
  display: grid;
  gap: 16px;
}
.osc-controls {
  display: grid;
  grid-template-columns: 180px 1fr;
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
