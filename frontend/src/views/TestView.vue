<template>
  <v-container class="py-6">
    <h1 class="text-h4 mb-6">测试页面（原始）</h1>
    <DeviceList />
    <Oscilloscope />
    <FrequencyView />
    <GraphEditor />
  </v-container>
</template>

<script setup lang="ts">
import DeviceList from '../components/DeviceList.vue';
import Oscilloscope from '../components/Oscilloscope.vue';
import FrequencyView from '../components/FrequencyView.vue';
import GraphEditor from '../components/GraphEditor.vue';
</script>
