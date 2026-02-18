<template>
  <ViewContainer>
    <v-container class="py-6">
      <h1 class="text-h4 mb-6">示波器</h1>
      <Oscilloscope />
      <FrequencyView />
    </v-container>
  </ViewContainer>
</template>

<script setup lang="ts">
import ViewContainer from '../components/ViewContainer.vue';
import Oscilloscope from '../components/Oscilloscope.vue';
import FrequencyView from '../components/FrequencyView.vue';
</script>
