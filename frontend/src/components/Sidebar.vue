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
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useSidebar } from '../composables/useSidebar';

const $route = useRoute();
const {
  sidebarState,
  toggleSidebar,
  expandSidebar,
  collapseSidebar,
  isMobile
} = useSidebar();

// 导航项配置
const navItems = [
  { title: '设备', path: '/devices', icon: 'mdi-devices' },
  { title: '示波器', path: '/oscilloscope', icon: 'mdi-oscilloscope' },
  { title: '可视化', path: '/visualization', icon: 'mdi-chart-line' },
  { title: '计算图', path: '/cpgraph', icon: 'mdi-graph-outline' },
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