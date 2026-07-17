<template>
  <v-app>
    <!-- 可折叠侧边栏 -->
    <Sidebar />
    
    <!-- 主内容区域 -->
    <v-main
      class="main-content"
      :class="{ 'full-height-content': $route.meta?.fullHeight }"
    >
      <div class="content-wrapper">
        <router-view />
      </div>
    </v-main>

    <!-- 通用底栏：性能监控 -->
    <StatusBar />

    <!-- 全局 Toast 通知 -->
    <div class="toast-container">
      <v-slide-y-reverse-transition group>
        <v-alert
          v-for="msg in toast.toasts.value"
          :key="msg.id"
          :type="msg.type"
          variant="tonal"
          closable
          density="compact"
          class="toast-item"
          @click:close="toast.dismiss(msg.id)"
        >
          {{ msg.text }}
        </v-alert>
      </v-slide-y-reverse-transition>
    </div>
  </v-app>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import StatusBar from './components/StatusBar.vue';
import { sessionStore } from './services/sessionStore';
import { graphRuntimeStore } from './services/graphRuntimeStore';
import { controlWebSocket } from './services/controlWebSocket';
import { useToast } from './composables/useToast';
import { useAppTheme } from './composables/useAppTheme';

const toast = useToast();
const { initTheme } = useAppTheme();

onMounted(() => {
  initTheme();
  sessionStore.startGlobalPolling();
  // 初始化控制 WS（替代运行时状态轮询）
  controlWebSocket.connect();
  graphRuntimeStore.init();
});

onUnmounted(() => {
  sessionStore.stopGlobalPolling();
  graphRuntimeStore.cleanup();
});
</script>

<style>
/* 全局样式调整 */
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
}

#app, .v-application {
  height: 100vh;
}

.v-application {
  display: flex;
  flex-direction: column;
}

.v-application--wrap {
  height: 100vh;
  min-height: 100vh;
}

/* 主内容区域样式 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto; /* 普通页面启用滚动 */
}

/* cpgraph: 精确占据剩余高度，不可滚动 */
.full-height-content {
  height: calc(100vh - 32px) !important;
  overflow: hidden !important;
  flex: none !important;
}

.full-height-content .content-wrapper {
  height: 100%;
  overflow: hidden;
}

/* 让 cpgraph 路由下 flex 容器链正确继承高度 */
.full-height-content .view-container,
.full-height-content .fullscreen-graph-editor,
.full-height-content .graph-content,
.full-height-content .graph-wrapper {
  height: 100% !important;
  min-height: 0 !important;
}

.full-height-content .palette,
.full-height-content .graph-container,
.full-height-content .sidebar {
  height: 100% !important;
}

/* 确保所有视图组件都能充分利用空间 */
.view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
}

/* 全局 Toast 通知样式 */
.toast-container {
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
  max-width: 400px;
}

.toast-item {
  pointer-events: auto;
  margin-bottom: 0 !important;
}

/* ===== 视觉打磨 ===== */

/* 主题切换时的平滑过渡 */
.v-application,
.v-application .v-toolbar,
.v-navigation-drawer,
.status-bar,
.palette,
.palette-title,
.palette-item,
.group-title,
.graph-wrapper,
.fullscreen-graph-editor,
.graph-toolbar,
.graph-container {
  transition: background-color 0.25s ease, border-color 0.25s ease, color 0.2s ease;
}

/* 细滚动条（WebKit） */
*::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

*::-webkit-scrollbar-track {
  background: transparent;
}

*::-webkit-scrollbar-thumb {
  background: rgba(var(--v-theme-on-surface), 0.18);
  border-radius: 4px;
}

*::-webkit-scrollbar-thumb:hover {
  background: rgba(var(--v-theme-on-surface), 0.32);
}

/* 细滚动条（Firefox） */
* {
  scrollbar-width: thin;
  scrollbar-color: rgba(var(--v-theme-on-surface), 0.18) transparent;
}
</style>
