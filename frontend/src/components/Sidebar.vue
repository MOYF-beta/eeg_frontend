<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="true"
    :permanent="true"
    :width="56"
    data-testid="sidebar-drawer"
    class="sidebar"
  >
    <!-- 导航菜单 -->
    <v-list density="compact" nav>
      <v-list-item
        v-for="item in navItems"
        :key="item.path"
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
              class="nav-item"
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
              :disabled="!isRunning"
              link
              class="nav-item"
              @click="toggleRecording"
            />
          </template>
          <span>{{ isRecording ? '停止录制' : '录制输出节点数据' }}</span>
        </v-tooltip>
      </div>
    </div>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { onMounted, onUnmounted } from 'vue';
import { graphRuntimeStore } from '../services/graphRuntimeStore';
import { useToast } from '../composables/useToast';

// 从graphRuntimeStore获取状态
const {
  isRunning,
  canRunGraph,
  runByMode,
  stopRun
} = graphRuntimeStore;

const toast = useToast();

// 录制状态
const isRecording = ref(false);

// 导航项配置
const navItems = [
  { title: '计算图工作台', path: '/cpgraph', icon: 'mdi-graph-outline' },
  { title: '可视化', path: '/visualization', icon: 'mdi-chart-line' },
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

// 切换录制
async function toggleRecording() {
  if (isRecording.value) {
    // 停止录制
    try {
      const resp = await fetch('/api/graph/record/', { method: 'DELETE' });
      const data = await resp.json();
      if (data.ok) {
        isRecording.value = false;
      }
    } catch (e) {
      console.error('[Sidebar] Failed to stop recording:', e);
    }
  } else {
    // 开始录制
    try {
      const resp = await fetch('/api/graph/record/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      const data = await resp.json();
      if (data.ok) {
        isRecording.value = true;
      }
    } catch (e) {
      console.error('[Sidebar] Failed to start recording:', e);
    }
  }
}

// 注：graphRuntimeStore 的 init/cleanup 由 App.vue 全权管理，
// Sidebar 不重复调用，避免在 Sidebar 卸载时误断全局 WebSocket 连接。
</script>

<style scoped>
.sidebar {
  transition: width 0.3s ease;
}

.nav-item {
  min-height: 48px;
}

/* 运行控制区域 */
.graph-controls {
  overflow: hidden;
}

/* 悬停效果 */
.nav-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

/* 激活状态 */
.nav-item.v-list-item--active {
  background-color: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}
</style>