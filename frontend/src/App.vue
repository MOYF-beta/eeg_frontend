<template>
  <v-app>
    <v-app-bar color="primary" prominent>
      <v-app-bar-title>EEG 基础前端</v-app-bar-title>
    </v-app-bar>
    <v-main>
      <v-container class="py-6">
        <DeviceList />
        <Oscilloscope />
        <FrequencyView />
        <GraphEditor />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import DeviceList from './components/DeviceList.vue';
import Oscilloscope from './components/Oscilloscope.vue';
import FrequencyView from './components/FrequencyView.vue';
import GraphEditor from './components/GraphEditor.vue';
</script>
