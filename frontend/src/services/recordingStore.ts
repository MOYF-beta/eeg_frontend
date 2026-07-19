/**
 * recordingStore — 全局录制状态（单例）
 *
 * 后端 POST/DELETE /api/graph/record/ 只切换状态，本 store 通过轮询
 * GET /api/graph/record/ 与后端对齐，供侧边栏按钮和状态栏显示。
 */

import { reactive } from 'vue';

export interface ActiveRecording {
  nodeId: string;
  filepath: string;
  format: string;
  sampleCount: number;
  duration: number;
}

interface RecordingState {
  recording: boolean;
  recordings: ActiveRecording[];
}

export const recordingState = reactive<RecordingState>({
  recording: false,
  recordings: [],
});

let pollTimer: number | null = null;
let subscriberCount = 0;

async function refresh() {
  try {
    const res = await fetch('/api/graph/record/');
    if (!res.ok) return;
    const data = await res.json();
    if (!data.ok) return;
    recordingState.recording = Boolean(data.recording);
    recordingState.recordings = Array.isArray(data.recordings) ? data.recordings : [];
  } catch {
    // 后端不可达时保持现状
  }
}

async function start(): Promise<boolean> {
  const res = await fetch('/api/graph/record/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  const data = await res.json();
  await refresh();
  return Boolean(data.ok);
}

async function stop(): Promise<boolean> {
  const res = await fetch('/api/graph/record/', { method: 'DELETE' });
  const data = await res.json();
  await refresh();
  return Boolean(data.ok);
}

/** 订阅录制状态（引用计数；首个订阅者启动轮询，最后一个退订后停止） */
function subscribe() {
  subscriberCount += 1;
  if (pollTimer === null) {
    refresh();
    pollTimer = window.setInterval(refresh, 2000);
  }
  return () => {
    subscriberCount = Math.max(0, subscriberCount - 1);
    if (subscriberCount === 0 && pollTimer !== null) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  };
}

export const recordingStore = {
  state: recordingState,
  refresh,
  start,
  stop,
  subscribe,
};

export default recordingStore;
