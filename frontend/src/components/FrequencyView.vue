<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title>频域显示（基础版）</v-card-title>
    <v-divider />
    <v-card-text>
      <v-row>
        <v-col v-for="band in bands" :key="band.name" cols="12" md="3">
          <v-card variant="outlined">
            <v-card-title>{{ band.name }}</v-card-title>
            <v-card-text class="text-h6">{{ band.value.toFixed(2) }}</v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const bands = ref([
  { name: 'Delta', value: 0.8 },
  { name: 'Theta', value: 1.2 },
  { name: 'Alpha', value: 0.6 },
  { name: 'Beta', value: 1.5 },
]);
</script>
