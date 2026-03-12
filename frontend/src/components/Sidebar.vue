<template>
  <v-navigation-drawer
    v-model="drawer"
    :rail="rail"
    :permanent="true"
    :width="sidebarWidth"
    class="sidebar"
  >
    <!-- 侧边栏头部 -->
    <v-list-item
      :title="rail ? '' : 'EEG 脑电系统'"
      class="sidebar-header"
      @click="toggleRail"
    >
      <template v-slot:prepend>
        <v-icon :icon="rail ? 'mdi-menu' : 'mdi-chevron-left'" />
      </template>
      <template v-slot:append v-if="!rail">
        <v-btn
          icon
          variant="text"
          size="small"
          @click.stop="toggleRail"
        >
          <v-icon>mdi-chevron-left</v-icon>
        </v-btn>
      </template>
    </v-list-item>

    <v-divider></v-divider>

    <!-- 导航菜单 -->
    <v-list density="compact" nav>
      <v-list-item
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :active="$route.path === item.path"
        :prepend-icon="item.icon"
        :title="rail ? '' : item.title"
        link
        class="nav-item"
        @click="handleNavClick"
      >
        <template v-slot:prepend v-if="rail">
          <v-icon :icon="item.icon" />
        </template>
      </v-list-item>
    </v-list>



    <!-- 计算图运行控制区域 -->
    <div class="graph-controls" :class="{ 'graph-controls-collapsed': rail }">
      <v-divider class="my-2" />
      
      <!-- 状态提示 -->
      <div v-if="!rail" class="px-3 py-2">
        <v-chip size="small" :color="isRunning ? 'warning' : (frozen ? 'info' : 'default')" class="mb-2">
          <v-icon size="small" class="mr-1">
            {{ isRunning ? 'mdi-play' : (frozen ? 'mdi-lock' : 'mdi-pencil') }}
          </v-icon>
          {{ statusDescription }}
        </v-chip>
      </div>
      
      <!-- 运行控制按钮 -->
      <div class="px-3 py-2">
        
        <!-- 运行按钮组 -->
        <div class="d-flex flex-column ga-2">
          <v-btn
            size="small"
            color="success"
            @click="handleRunClick('live')"
            :disabled="!canRunGraph"
            :title="!canRunGraph ? '计算图正在运行中' : 'Live运行计算图'"
            block
          >
            <v-icon left size="small" class="mr-1">mdi-play</v-icon>
            <span v-if="!rail">Live运行</span>
          </v-btn>
          <v-btn
            size="small"
            color="secondary"
            @click="handleRunClick('offline')"
            :disabled="!canRunGraph"
            :title="!canRunGraph ? '计算图正在运行中' : '离线运行计算图'"
            block
          >
            <v-icon left size="small" class="mr-1">mdi-file-sync</v-icon>
            <span v-if="!rail">离线运行</span>
          </v-btn>
          <v-btn
            size="small"
            color="error"
            @click="stopRun"
            :disabled="!isRunning"
            :title="!isRunning ? '计算图未运行' : '停止运行计算图'"
            block
          >
            <v-icon left size="small" class="mr-1">mdi-stop</v-icon>
            <span v-if="!rail">停止</span>
          </v-btn>
        </div>
        
        <!-- 运行状态提示 -->
        <div v-if="isRunning && !rail" class="mt-2">
          <v-chip size="small" color="success" class="mb-1">
            <v-icon size="small" class="mr-1">mdi-check-circle</v-icon>
            {{ runtimeMode === 'offline' ? '离线运行中' : 'Live运行中' }}
          </v-chip>
          
          <!-- 离线进度条 -->
          <div v-if="isRunning && runtimeMode === 'offline'" class="mt-1">
            <div class="d-flex justify-space-between text-caption mb-1">
              <span>离线处理进度</span>
              <span>{{ offlineProgress.toFixed(1) }}%</span>
            </div>
            <v-progress-linear :model-value="offlineProgress" color="secondary" height="8" rounded />
          </div>
          
          <!-- 延迟和非实时提示 -->
          <div v-if="processingDelayMs > 0 || nonRealtime" class="mt-1">
            <v-chip v-if="processingDelayMs > 0" size="small" :color="nonRealtime ? 'warning' : 'info'" class="mr-1 mb-1">
              延迟 {{ processingDelayMs }}ms
            </v-chip>
            <v-chip v-if="nonRealtime" size="small" color="warning" class="mb-1">
              非实时
            </v-chip>
          </div>
        </div>
        
        <!-- 运行时警告 -->
        <v-alert
          v-if="runtimeWarning && !rail"
          type="warning"
          density="compact"
          variant="tonal"
          class="mt-2"
        >
          {{ runtimeWarning }}
        </v-alert>
      </div>
    </div>

    <!-- 折叠/展开按钮（固定在底部） -->
    <template v-slot:append>
      <v-list-item
        :title="rail ? '' : '折叠侧边栏'"
        @click="toggleRail"
        class="toggle-button"
      >
        <template v-slot:prepend>
          <v-icon :icon="rail ? 'mdi-chevron-right' : 'mdi-chevron-left'" />
        </template>
      </v-list-item>
    </template>
  </v-navigation-drawer>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useSidebar } from '../composables/useSidebar';
import { graphRuntimeStore } from '../services/graphRuntimeStore';

const $route = useRoute();
const {
  sidebarState,
  toggleSidebar,
  expandSidebar,
  collapseSidebar,
  isMobile
} = useSidebar();

// 从graphRuntimeStore获取状态
const {
  isRunning,
  runtimeMode,
  frozen,
  offlineProgress,
  processingDelayMs,
  nonRealtime,
  runtimeWarning,
  canRunGraph,
  statusDescription,
  runByMode,
  stopRun
} = graphRuntimeStore;

// 导航项配置
const navItems = [
  { title: '设备', path: '/devices', icon: 'mdi-devices' },
  { title: '示波器', path: '/oscilloscope', icon: 'mdi-oscilloscope' },
  { title: '可视化', path: '/visualization', icon: 'mdi-chart-line' },
  { title: '计算图', path: '/cpgraph', icon: 'mdi-graph-outline' },
  { title: '串口调试', path: '/serial-debug', icon: 'mdi-console-line' },
  { title: '测试', path: '/test', icon: 'mdi-test-tube' },
];

// 计算侧边栏属性
const drawer = computed(() => true); // 始终显示
const rail = computed(() => sidebarState.value.isRail);
const sidebarWidth = computed(() => sidebarState.value.width);

// 切换折叠状态
const toggleRail = () => {
  toggleSidebar();
};

// 点击导航项时，在移动设备上自动折叠侧边栏
const handleNavClick = () => {
  if (isMobile.value) {
    collapseSidebar();
  }
};

// 运行按钮点击处理
async function handleRunClick(mode: 'live' | 'offline') {
  try {
    await runByMode(mode);
  } catch (err) {
    console.error(`[Sidebar] Failed to run graph in ${mode} mode:`, err);
    alert(`运行计算图失败: ${err instanceof Error ? err.message : '未知错误'}`);
  }
}

// 初始化graphRuntimeStore
import { onMounted, onUnmounted } from 'vue';
onMounted(() => {
  graphRuntimeStore.init();
});

onUnmounted(() => {
  graphRuntimeStore.cleanup();
});
</script>

<style scoped>
.sidebar {
  transition: width 0.3s ease;
}

.sidebar-header {
  min-height: 64px;
  cursor: pointer;
}

.nav-item {
  min-height: 48px;
}

.toggle-button {
  border-top: 1px solid rgba(0, 0, 0, 0.12);
  cursor: pointer;
}

/* 冻结开关容器 */
.freeze-switch-container {
  transition: all 0.3s ease;
}

.freeze-switch {
  min-width: 0;
}

/* 运行控制区域 */
.graph-controls {
  transition: all 0.3s ease;
  overflow: hidden;
}

.graph-controls-collapsed {
  opacity: 0;
  height: 0;
  padding: 0 !important;
  margin: 0 !important;
}

/* 悬停效果（仅背景色变化，不展开） */
.nav-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

/* 激活状态 */
.nav-item.v-list-item--active {
  background-color: rgba(var(--v-theme-primary), 0.08);
  color: rgb(var(--v-theme-primary));
}

/* 响应式设计 */
@media (max-width: 960px) {
  .sidebar {
    width: 56px !important;
  }
  
  .sidebar:not(.v-navigation-drawer--rail) {
    width: 256px !important;
  }
}
</style>