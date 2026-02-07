<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title>频域显示（频谱图）</v-card-title>
    <v-divider />
    <v-card-text>
      <div class="spec-wrap">
        <canvas ref="canvasRef" class="spec-canvas"></canvas>
        <div class="spec-footer">
          <div>采样率：{{ sampleRate }} Hz</div>
          <div>窗口：{{ bufferSize }} 点</div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue';
import { createEegSocket, type EegPacket } from '../services/ws';

const sampleRate = 250;
const bufferSize = 256;
const spectrum = ref<number[]>(Array.from({ length: bufferSize / 2 }, () => 0));
const samples = ref<number[]>([]);
const canvasRef = ref<HTMLCanvasElement | null>(null);
let ws: WebSocket | null = null;
let resizeObserver: ResizeObserver | null = null;
let animationId = 0;
let lastComputeTime = 0;

const computeSpectrum = () => {
  if (samples.value.length < bufferSize) return;
  const x = samples.value.slice(-bufferSize);
  const mags = new Array(bufferSize / 2).fill(0);
  for (let k = 0; k < bufferSize / 2; k += 1) {
    let re = 0;
    let im = 0;
    for (let n = 0; n < bufferSize; n += 1) {
      const w = 0.5 * (1 - Math.cos((2 * Math.PI * n) / (bufferSize - 1)));
      const angle = (2 * Math.PI * k * n) / bufferSize;
      const xn = x[n] * w;
      re += xn * Math.cos(angle);
      im -= xn * Math.sin(angle);
    }
    mags[k] = Math.sqrt(re * re + im * im) / bufferSize;
  }
  spectrum.value = mags;
};

const resizeCanvas = () => {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 600;
  const height = canvas.clientHeight || 240;
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
  const height = canvas.clientHeight || 240;
  const leftPad = 48;
  const rightPad = 12;
  const topPad = 10;
  const bottomPad = 24;
  const plotWidth = width - leftPad - rightPad;
  const plotHeight = height - topPad - bottomPad;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = topPad + (i / 4) * plotHeight;
    ctx.beginPath();
    ctx.moveTo(leftPad, y);
    ctx.lineTo(leftPad + plotWidth, y);
    ctx.stroke();
  }

  for (let i = 0; i <= 4; i += 1) {
    const x = leftPad + (i / 4) * plotWidth;
    ctx.beginPath();
    ctx.moveTo(x, topPad);
    ctx.lineTo(x, topPad + plotHeight);
    ctx.stroke();
  }

  const mags = spectrum.value;
  const maxMag = Math.max(...mags, 0.001);
  ctx.strokeStyle = '#7e57c2';
  ctx.lineWidth = 2;
  ctx.beginPath();
  mags.forEach((m, idx) => {
    const x = leftPad + (idx / (mags.length - 1)) * plotWidth;
    const y = topPad + plotHeight - (m / maxMag) * (plotHeight - 4);
    if (idx === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = '#546e7a';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'center';
  for (let i = 0; i <= 4; i += 1) {
    const x = leftPad + (i / 4) * plotWidth;
    const hz = ((sampleRate / 2) * (i / 4)).toFixed(0);
    ctx.fillText(hz, x, height - 6);
  }
  ctx.textAlign = 'left';
  ctx.fillText('Hz', leftPad + plotWidth + 4, height - 6);

  ctx.textAlign = 'right';
  for (let i = 0; i <= 4; i += 1) {
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
};

const loop = () => {
  drawSpectrum();
  animationId = requestAnimationFrame(loop);
};

onMounted(() => {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.hostname || 'localhost';
  const url = `${protocol}://${host}:8000/ws/stream/`;
  ws = createEegSocket(url, (packet: EegPacket) => {
    const value = packet.channels?.[0] ?? 0;
    samples.value.push(value);
    if (samples.value.length > bufferSize * 4) {
      samples.value.splice(0, samples.value.length - bufferSize * 4);
    }
    const now = performance.now();
    if (now - lastComputeTime > 200) {
      lastComputeTime = now;
      computeSpectrum();
    }
  });

  resizeObserver = new ResizeObserver(() => resizeCanvas());
  if (canvasRef.value) {
    resizeObserver.observe(canvasRef.value);
    resizeCanvas();
  }
  animationId = requestAnimationFrame(loop);
});

onUnmounted(() => {
  ws?.close();
  if (resizeObserver && canvasRef.value) resizeObserver.unobserve(canvasRef.value);
  if (animationId) cancelAnimationFrame(animationId);
});
</script>

<style scoped>
.spec-wrap {
  display: grid;
  gap: 8px;
}
.spec-canvas {
  width: 100%;
  height: 260px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  display: block;
}
.spec-footer {
  display: flex;
  gap: 16px;
  color: #666;
  font-size: 12px;
}
</style>
