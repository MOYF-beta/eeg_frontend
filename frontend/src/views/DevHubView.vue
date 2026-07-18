<template>
  <ViewContainer>
    <v-container class="py-6">
      <h1 class="text-h4 mb-4">开发工具目录</h1>
      <v-list class="border rounded" lines="two">
        <v-list-item to="/devices" prepend-icon="mdi-devices" title="设备管理" subtitle="模拟与真实设备管理" />
        <v-list-item to="/dev/serial-debug" prepend-icon="mdi-console-line" title="设备调试" subtitle="任意驱动的原始输出与数据帧诊断" />
      </v-list>
    </v-container>
  </ViewContainer>
</template>

<script setup lang="ts">
import ViewContainer from '../components/ViewContainer.vue';
</script>
