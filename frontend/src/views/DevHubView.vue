<template>
  <ViewContainer>
    <v-container class="py-6">
      <h1 class="text-h4 mb-4">开发工具目录</h1>
      <v-list class="border rounded" lines="two">
        <v-list-item to="/dev/serial-debug" prepend-icon="mdi-console-line" title="串口调试" subtitle="真实设备串口调试与状态诊断" />
        <v-list-item to="/dev/test" prepend-icon="mdi-test-tube" title="测试页面" subtitle="开发期调试组件与场景测试" />
      </v-list>
    </v-container>
  </ViewContainer>
</template>

<script setup lang="ts">
import ViewContainer from '../components/ViewContainer.vue';
</script>
