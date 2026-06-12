<template>
  <v-app>
    <!-- 可折叠侧边栏 -->
    <Sidebar />
    
    <!-- 主内容区域 -->
    <v-main class="main-content">
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
  overflow: auto; /* 启用滚动 */
}

.v-application {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* 主内容区域样式 */
.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: auto; /* 启用滚动 */
}

/* 内容包装器 */
.content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 确保flex容器可以收缩 */
}

/* Vuetify的v-navigation-drawer会自动处理布局，不需要手动设置margin */
/* 侧边栏使用绝对定位，不会占用文档流空间 */

/* 确保内容区域在侧边栏存在时也能充分利用空间 */
.v-application--wrap {
  min-height: 100vh;
}

/* 确保主内容区域宽度正确 */
.v-main {
  width: 100%;
}

/* 当侧边栏展开时，Vuetify会自动调整内容区域 */
/* 我们只需要确保内容区域内的组件能充分利用空间 */

/* 确保所有视图组件都能充分利用空间 */
.view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
}
</style>
