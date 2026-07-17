<template>
  <div class="simulated-device-config">
    <!-- 全局噪声配置 -->
    <v-expansion-panels v-if="showGlobalNoise" class="mb-4">
      <v-expansion-panel>
        <v-expansion-panel-title>
          <v-icon left>mdi-sine-wave</v-icon>
          全局噪声配置
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <noise-config-editor
            v-model="config.globalNoise"
            :label="'全局噪声'"
          />
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- 通道配置 -->
    <v-expansion-panels multiple class="mb-4">
      <v-expansion-panel
        v-for="(channel, index) in config.channels"
        :key="index"
      >
        <v-expansion-panel-title>
          <v-icon left>mdi-chart-line</v-icon>
          通道 {{ index + 1 }}
          <v-chip
            v-if="!channel.enabled"
            size="small"
            color="grey"
            class="ml-2"
          >
            禁用
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="channel-config">
            <!-- 通道启用开关 -->
            <v-switch
              v-model="channel.enabled"
              label="启用此通道"
              density="compact"
              class="mb-4"
            />

            <div v-if="channel.enabled">
              <!-- 信号配置 -->
              <v-card variant="outlined" class="mb-4">
                <v-card-title class="text-subtitle-1">
                  <v-icon left>mdi-waveform</v-icon>
                  信号配置
                </v-card-title>
                <v-card-text>
                  <signal-config-editor
                    v-model="channel.signal"
                    :channel-index="index"
                  />
                </v-card-text>
              </v-card>

              <!-- 噪声配置 -->
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  <v-icon left>mdi-chart-bell-curve</v-icon>
                  噪声配置
                </v-card-title>
                <v-card-text>
                  <noise-config-editor
                    v-model="channel.noise"
                    :label="`通道 ${index + 1} 噪声`"
                  />
                </v-card-text>
              </v-card>
            </div>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <!-- 快速配置按钮 -->
    <div class="d-flex flex-wrap ga-2 mb-4">
      <v-btn
        size="small"
        variant="tonal"
        @click="applyToAllChannels"
      >
        <v-icon left>mdi-content-copy</v-icon>
        应用到所有通道
      </v-btn>
      <v-btn
        size="small"
        variant="tonal"
        @click="resetAllChannels"
      >
        <v-icon left>mdi-refresh</v-icon>
        重置所有通道
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import type { SimulatedDeviceConfig, ChannelConfig, SignalConfig, NoiseConfig } from '../services/sessionStore';
import SignalConfigEditor from './SignalConfigEditor.vue';
import NoiseConfigEditor from './NoiseConfigEditor.vue';

const props = defineProps<{
  modelValue: SimulatedDeviceConfig;
  channelCount: number;
  showGlobalNoise?: boolean;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: SimulatedDeviceConfig];
}>();

const config = ref<SimulatedDeviceConfig>({
  channels: [],
  globalNoise: props.modelValue.globalNoise
});

// 初始化通道配置
const initializeChannels = () => {
  const channels: ChannelConfig[] = [];
  for (let i = 0; i < props.channelCount; i++) {
    if (props.modelValue.channels[i]) {
      channels.push({ ...props.modelValue.channels[i] });
    } else {
      channels.push({
        index: i,
        enabled: true,
        signal: {
          type: 'sine',
          frequency: 10,
          amplitude: 100,
          phase: 0
        },
        noise: {
          type: 'none',
          amplitude: 0
        }
      });
    }
  }
  config.value.channels = channels;
};

// 监听 channelCount 变化
watch(() => props.channelCount, () => {
  initializeChannels();
}, { immediate: true });

// 监听配置变化并向上传递
watch(config, (newConfig) => {
  emit('update:modelValue', newConfig);
}, { deep: true });

// 应用到所有通道
const applyToAllChannels = () => {
  if (config.value.channels.length === 0) return;
  
  const firstChannel = config.value.channels[0];
  if (!firstChannel.enabled) return;
  
  for (let i = 1; i < config.value.channels.length; i++) {
    config.value.channels[i] = {
      ...config.value.channels[i],
      signal: { ...firstChannel.signal },
      noise: firstChannel.noise ? { ...firstChannel.noise } : undefined
    };
  }
};

// 重置所有通道
const resetAllChannels = () => {
  config.value.channels.forEach((channel, index) => {
    config.value.channels[index] = {
      index,
      enabled: true,
      signal: {
        type: 'sine',
        frequency: 10,
        amplitude: 100,
        phase: 0
      },
      noise: {
        type: 'none',
        amplitude: 0
      }
    };
  });
};
</script>

<style scoped>
.channel-config {
  padding: 8px 0;
}

.simulated-device-config {
  max-height: 600px;
  overflow-y: auto;
}
</style>