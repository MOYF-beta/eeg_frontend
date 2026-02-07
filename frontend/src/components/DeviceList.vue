<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      设备列表
      <v-btn color="primary" @click="addMockDevice">添加设备</v-btn>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <v-row>
        <v-col
          v-for="device in devices"
          :key="device.id"
          cols="12"
          md="6"
        >
          <v-card variant="outlined">
            <v-card-title>{{ device.name }}</v-card-title>
            <v-card-subtitle>{{ device.address }}</v-card-subtitle>
            <v-card-text class="text-body-2">
              通道：{{ device.channels.join(', ') }}
            </v-card-text>
            <v-card-actions>
              <v-btn size="small" @click="selectDevice(device.id)">查看</v-btn>
            </v-card-actions>
          </v-card>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';

type Device = {
  id: string;
  name: string;
  address: string;
  channels: string[];
};

const devices = ref<Device[]>([
  {
    id: 'mock-1',
    name: '模拟设备 1',
    address: 'COM3',
    channels: ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'],
  },
]);

const addMockDevice = () => {
  devices.value.push({
    id: `mock-${devices.value.length + 1}`,
    name: `模拟设备 ${devices.value.length + 1}`,
    address: `COM${devices.value.length + 3}`,
    channels: ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'],
  });
};

const selectDevice = (id: string) => {
  console.log('select device', id);
};
</script>
