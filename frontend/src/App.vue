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
  </v-app>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import Sidebar from './components/Sidebar.vue';
import StatusBar from './components/StatusBar.vue';
import { sessionStore } from './services/sessionStore';

onMounted(() => {
  sessionStore.startGlobalPolling();
});

onUnmounted(() => {
  sessionStore.stopGlobalPolling();
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
</style>
