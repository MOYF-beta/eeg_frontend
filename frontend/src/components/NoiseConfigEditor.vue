<template>
  <div class="noise-config-editor">
    <!-- 噪声类型选择 -->
    <v-select
      v-model="noise.type"
      :items="noiseTypes"
      label="噪声类型"
      density="compact"
      variant="outlined"
      class="mb-3"
    >
      <template v-slot:item="{ props: itemProps, item }">
        <v-list-item v-bind="itemProps">
          <template v-slot:prepend>
            <v-icon :icon="getNoiseIcon(item.value)" />
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </template>
    </v-select>

    <!-- 噪声幅度 -->
    <v-text-field
      v-model.number="noise.amplitude"
      label="噪声幅度"
      type="number"
      density="compact"
      variant="outlined"
      class="mb-3"
      :min="0"
      :max="1000"
      :step="1"
      :disabled="noise.type === 'none'"
    />

    <!-- 噪声特定参数 -->
    <div v-if="noise.type !== 'none'">
      <!-- 随机种子 -->
      <v-text-field
        v-model.number="noise.seed"
        label="随机种子"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :min="1"
        :max="999999"
        :step="1"
        placeholder="留空使用随机种子"
      />

      <!-- 截止频率（用于有色噪声） -->
      <div v-if="noise.type === 'pink' || noise.type === 'brownian'">
        <v-text-field
          v-model.number="noise.cutoffFrequency"
          label="截止频率 (Hz)"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :min="0.1"
          :max="1000"
          :step="0.1"
          suffix="Hz"
        />
      </div>

      <!-- 高斯噪声标准差 -->
      <div v-if="noise.type === 'gaussian'">
        <v-text-field
          v-model.number="noise.amplitude"
          label="标准差"
          type="number"
          density="compact"
          variant="outlined"
          class="mb-3"
          :min="0"
          :max="1000"
          :step="0.1"
        />
      </div>

      <!-- 预览信息 -->
      <v-alert type="info" variant="tonal" density="compact" class="mt-3">
        <div class="d-flex align-center">
          <v-icon class="mr-2">mdi-information</v-icon>
          <span>{{ previewInfo }}</span>
        </div>
      </v-alert>
    </div>

    <!-- 无噪声提示 -->
    <v-alert v-if="noise.type === 'none'" type="info" variant="tonal" density="compact">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-check-circle</v-icon>
        <span>此通道不添加噪声</span>
      </div>
    </v-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import type { NoiseConfig } from '../services/sessionStore';

const props = defineProps<{
  modelValue?: NoiseConfig;
  label?: string;
}>();

const emit = defineEmits<{
  'update:modelValue': [value?: NoiseConfig];
}>();

const noise = ref<NoiseConfig>({
  type: 'none',
  amplitude: 0
});

// 初始化噪声配置
watch(() => props.modelValue, (newValue) => {
  if (newValue) {
    noise.value = { ...newValue };
  } else {
    noise.value = { type: 'none', amplitude: 0 };
  }
}, { immediate: true });

// 监听噪声变化并向上传递
watch(noise.value, (newNoise) => {
  if (newNoise.type === 'none' && newNoise.amplitude === 0) {
    emit('update:modelValue', undefined);
  } else {
    emit('update:modelValue', newNoise);
  }
}, { deep: true });

// 噪声类型选项
const noiseTypes = [
  { title: '无噪声', value: 'none' },
  { title: '白噪声', value: 'white' },
  { title: '粉红噪声', value: 'pink' },
  { title: '布朗噪声', value: 'brownian' },
  { title: '高斯噪声', value: 'gaussian' }
];

// 获取噪声图标
const getNoiseIcon = (type: string) => {
  switch (type) {
    case 'none': return 'mdi-check-circle-outline';
    case 'white': return 'mdi-chart-scatter-plot';
    case 'pink': return 'mdi-chart-bell-curve';
    case 'brownian': return 'mdi-chart-timeline';
    case 'gaussian': return 'mdi-chart-bell-curve-cumulative';
    default: return 'mdi-chart-line';
  }
};

// 预览信息
const previewInfo = computed(() => {
  const labelText = props.label ? `${props.label}: ` : '';
  
  switch (noise.value.type) {
    case 'white':
      return `${labelText}白噪声，幅度 ${noise.value.amplitude}`;
    case 'pink':
      return `${labelText}粉红噪声，幅度 ${noise.value.amplitude}${noise.value.cutoffFrequency ? `，截止频率 ${noise.value.cutoffFrequency}Hz` : ''}`;
    case 'brownian':
      return `${labelText}布朗噪声，幅度 ${noise.value.amplitude}${noise.value.cutoffFrequency ? `，截止频率 ${noise.value.cutoffFrequency}Hz` : ''}`;
    case 'gaussian':
      return `${labelText}高斯噪声，标准差 ${noise.value.amplitude}`;
    default:
      return `${labelText}${noise.value.type}噪声`;
  }
});
</script>

<style scoped>
.noise-config-editor {
  min-width: 300px;
}
</style>