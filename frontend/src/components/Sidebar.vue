<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="true"
    :permanent="true"
    :width="56"
    data-testid="sidebar-drawer"
    class="sidebar"
  >
    <div class="sidebar-layout">
      <!-- 应用标识 -->
      <div class="app-logo" title="EEG 工作台">
        <v-icon color="primary" size="26">mdi-brain</v-icon>
      </div>

      <!-- 导航菜单 -->
      <v-list density="compact" nav class="nav-list">
        <v-tooltip
          v-for="item in navItems"
          :key="item.path"
          location="right"
          :text="item.title"
        >
          <template #activator="{ props: tooltipProps }">
            <v-list-item
              v-bind="tooltipProps"
              :to="item.path"
              :active="$route.path === item.path"
              title=""
              link
              class="nav-item"
            >
              <template #prepend>
                <v-icon :icon="item.icon" />
              </template>
            </v-list-item>
          </template>
        </v-tooltip>
      </v-list>

      <!-- 运行控制区域 -->
      <div class="graph-controls">
        <v-divider class="my-2" />

        <!-- 控制按钮 -->
        <div class="graph-controls-buttons">
          <v-tooltip location="right">
            <template #activator="{ props: tooltipProps }">
              <v-list-item
                v-bind="tooltipProps"
                :title="isRunning ? '停止' : '运行'"
                :prepend-icon="isRunning ? 'mdi-stop' : 'mdi-play'"
                :disabled="!canRunGraph && !isRunning"
                link
                class="nav-item run-item"
                :class="{ 'run-item-active': isRunning }"
                data-testid="sidebar-run-toggle-btn"
                @click="isRunning ? stopRun() : handleRunClick('live')"
              />
            </template>
            <span>{{ isRunning ? '停止运行' : 'Live/实时运行' }}</span>
          </v-tooltip>

          <v-tooltip location="right">
            <template #activator="{ props: tooltipProps }">
              <v-list-item
                v-bind="tooltipProps"
                :title="isRecording ? '停止录制' : '录制'"
                :prepend-icon="isRecording ? 'mdi-stop-circle' : 'mdi-record-circle'"
                :disabled="!isRunning && (!canRunGraph || recordBusy)"
                link
                class="nav-item record-item"
                :class="{ 'record-item-active': isRecording }"
                data-testid="sidebar-record-btn"
                @click="toggleRecording"
              />
            </template>
            <span>{{ isRecording ? '停止录制' : (isRunning ? '录制输出节点数据' : '开始运行并录制') }}</span>
          </v-tooltip>
        </div>
      </div>

      <v-spacer />

      <!-- 主题切换 -->
      <div class="theme-toggle">
        <v-divider class="my-2" />
        <v-tooltip location="right">
          <template #activator="{ props: tooltipProps }">
            <v-list-item
              v-bind="tooltipProps"
              :title="isDark ? '切换到浅色模式' : '切换到深色模式'"
              :prepend-icon="isDark ? 'mdi-weather-sunny' : 'mdi-weather-night'"
              link
              class="nav-item"
              data-testid="sidebar-theme-toggle-btn"
              @click="toggleTheme"
            />
          </template>
          <span>{{ isDark ? '浅色模式' : '深色模式' }}</span>
        </v-tooltip>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { onMounted, onUnmounted } from 'vue';
import { graphRuntimeStore } from '../services/graphRuntimeStore';
import { recordingStore } from '../services/recordingStore';
import { useToast } from '../composables/useToast';
import { useAppTheme } from '../composables/useAppTheme';

const { isDark, toggleTheme } = useAppTheme();

// 从graphRuntimeStore获取状态
const {
  isRunning,
  canRunGraph,
  runByMode,
  stopRun
} = graphRuntimeStore;

const toast = useToast();

// 录制状态（全局共享，与后端轮询同步）
const isRecording = computed(() => recordingStore.state.recording);
const recordBusy = ref(false);
let unsubRecording: (() => void) | null = null;

onMounted(() => {
  unsubRecording = recordingStore.subscribe();
});
onUnmounted(() => {
  unsubRecording?.();
});

// 导航项配置
const navItems = [
  { title: '计算图工作台', path: '/cpgraph', icon: 'mdi-graph-outline' },
  { title: '可视化', path: '/visualization', icon: 'mdi-chart-line' },
  { title: '设备管理', path: '/devices', icon: 'mdi-devices' },
  { title: '开发目录', path: '/dev', icon: 'mdi-folder-wrench' },
];

// 始终显示
const drawer = ref(true);

// 运行按钮点击处理
async function handleRunClick(mode: 'live' | 'offline') {
  try {
    await runByMode(mode);
  } catch (err) {
    console.error(`[Sidebar] Failed to run graph in ${mode} mode:`, err);
    toast.show(`运行计算图失败: ${err instanceof Error ? err.message : '未知错误'}`, 'error');
  }
}

// 切换录制：未运行时先启动运行再开始录制
async function toggleRecording() {
  if (recordBusy.value) return;
  recordBusy.value = true;
  try {
    if (isRecording.value) {
      const ok = await recordingStore.stop();
      if (!ok) toast.show('停止录制失败', 'error');
    } else {
      if (!isRunning.value) {
        await runByMode('live');
        // 等待后端进入运行态，确保 ws/eeg/ 数据流已建立
        const deadline = Date.now() + 8000;
        while (!isRunning.value && Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, 100));
        }
        if (!isRunning.value) {
          toast.show('启动运行超时，无法开始录制', 'error');
          return;
        }
      }
      const ok = await recordingStore.start();
      if (!ok) toast.show('开始录制失败', 'error');
    }
  } catch (e) {
    console.error('[Sidebar] Failed to toggle recording:', e);
    toast.show(`录制操作失败: ${e instanceof Error ? e.message : '未知错误'}`, 'error');
  } finally {
    recordBusy.value = false;
  }
}

// 注：graphRuntimeStore 的 init/cleanup 由 App.vue 全权管理，
// Sidebar 不重复调用，避免在 Sidebar 卸载时误断全局 WebSocket 连接。
</script>

<style scoped>
.sidebar {
  transition: width 0.3s ease;
}

.sidebar-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* 应用标识 */
.app-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 52px;
  flex-shrink: 0;
}

.nav-list {
  flex-shrink: 0;
}

.nav-item {
  min-height: 44px;
  border-radius: 10px;
  margin: 2px 6px;
  transition: background-color 0.18s ease, color 0.18s ease;
}

/* 运行控制区域 */
.graph-controls {
  overflow: hidden;
}

/* 悬停效果（同时兼容亮/暗主题） */
.nav-item:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.06);
}

/* 激活状态 */
.nav-item.v-list-item--active {
  background-color: rgba(var(--v-theme-primary), 0.14);
  color: rgb(var(--v-theme-primary));
}

/* 运行/录制状态强调色 */
.run-item-active {
  color: rgb(var(--v-theme-warning)) !important;
}

.record-item-active {
  color: rgb(var(--v-theme-error)) !important;
}

.theme-toggle {
  flex-shrink: 0;
}
</style>