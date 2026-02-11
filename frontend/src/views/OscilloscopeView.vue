<template>
  <v-container class="py-6">
    <h1 class="text-h4 mb-6">示波器</h1>
    <Oscilloscope />
    <FrequencyView />
  </v-container>
</template>

<script setup lang="ts">
import Oscilloscope from '../components/Oscilloscope.vue';
import FrequencyView from '../components/FrequencyView.vue';
</script>
