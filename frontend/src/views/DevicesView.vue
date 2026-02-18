<template>
  <ViewContainer>
    <v-container class="py-6">
      <h1 class="text-h4 mb-6">设备管理</h1>
      <DeviceList />
    </v-container>
  </ViewContainer>
</template>

<script setup lang="ts">
import ViewContainer from '../components/ViewContainer.vue';
import DeviceList from '../components/DeviceList.vue';
</script>
