<template>
  <div class="signal-config-editor">
    <!-- 信号类型选择 -->
    <v-select
      v-model="signal.type"
      :items="signalTypes"
      label="信号类型"
      density="compact"
      variant="outlined"
      class="mb-3"
    >
      <template v-slot:item="{ props: itemProps, item }">
        <v-list-item v-bind="itemProps">
          <template v-slot:prepend>
            <v-icon :icon="getSignalIcon(item.value)" />
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </template>
    </v-select>

    <!-- 基本参数 -->
    <v-row>
      <v-col cols="6">
        <v-text-field
          v-model.number="signal.frequency"
          label="频率 (Hz)"
          type="number"
          density="compact"
          variant="outlined"
          :min="0.1"
          :max="1000"
          :step="0.1"
          suffix="Hz"
        />
      </v-col>
      <v-col cols="6">
        <v-text-field
          v-model.number="signal.amplitude"
          label="幅度"
          type="number"
          density="compact"
          variant="outlined"
          :min="0"
          :max="1000"
          :step="1"
        />
      </v-col>
    </v-row>

    <!-- 相位配置 -->
    <v-text-field
      v-model.number="signal.phase"
      label="相位 (度)"
      type="number"
      density="compact"
      variant="outlined"
      class="mb-3"
      :min="0"
      :max="360"
      :step="1"
      suffix="°"
    />

    <!-- 信号特定参数 -->
    <div v-if="signal.type === 'square' || signal.type === 'pulse'">
      <v-slider
        v-model.number="signal.dutyCycle"
        label="占空比"
        :min="0"
        :max="1"
        :step="0.01"
        class="mb-3"
      >
        <template v-slot:append>
          <span class="text-caption">{{ ((signal.dutyCycle || 0.5) * 100).toFixed(0) }}%</span>
        </template>
      </v-slider>
    </div>

    <div v-if="signal.type === 'pulse'">
      <v-text-field
        v-model.number="signal.pulseWidth"
        label="脉冲宽度 (秒)"
        type="number"
        density="compact"
        variant="outlined"
        class="mb-3"
        :min="0.001"
        :max="1"
        :step="0.001"
        suffix="s"
      />
    </div>

    <!-- 多个正弦波叠加配置 -->
    <div v-if="signal.type === 'multi_sine'">
      <v-expansion-panels class="mb-3">
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon left>mdi-plus-circle-multiple</v-icon>
            正弦波分量配置
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div v-for="(component, index) in signal.sineComponents" :key="index" class="mb-4">
              <v-card variant="outlined">
                <v-card-title class="text-subtitle-1">
                  分量 {{ index + 1 }}
                  <v-spacer />
                  <v-btn
                    v-if="signal.sineComponents.length > 1"
                    size="small"
                    icon
                    variant="text"
                    color="error"
                    @click="removeSineComponent(index)"
                  >
                    <v-icon>mdi-delete</v-icon>
                  </v-btn>
                </v-card-title>
                <v-card-text>
                  <v-row>
                    <v-col cols="4">
                      <v-text-field
                        v-model.number="component.frequency"
                        label="频率 (Hz)"
                        type="number"
                        density="compact"
                        variant="outlined"
                        :min="0.1"
                        :max="1000"
                        :step="0.1"
                      />
                    </v-col>
                    <v-col cols="4">
                      <v-text-field
                        v-model.number="component.amplitude"
                        label="幅度"
                        type="number"
                        density="compact"
                        variant="outlined"
                        :min="0"
                        :max="1000"
                        :step="1"
                      />
                    </v-col>
                    <v-col cols="4">
                      <v-text-field
                        v-model.number="component.phase"
                        label="相位 (度)"
                        type="number"
                        density="compact"
                        variant="outlined"
                        :min="0"
                        :max="360"
                        :step="1"
                      />
                    </v-col>
                  </v-row>
                </v-card-text>
              </v-card>
            </div>
            
            <v-btn
              size="small"
              variant="tonal"
              @click="addSineComponent"
            >
              <v-icon left>mdi-plus</v-icon>
              添加正弦波分量
            </v-btn>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </div>

    <!-- 预览信息 -->
    <v-alert v-if="previewInfo" type="info" variant="tonal" density="compact" class="mt-3">
      <div class="d-flex align-center">
        <v-icon class="mr-2">mdi-information</v-icon>
        <span>{{ previewInfo }}</span>
      </div>
    </v-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import type { SignalConfig } from '../services/sessionStore';

const props = defineProps<{
  modelValue: SignalConfig;
  channelIndex?: number;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: SignalConfig];
}>();

const signal = ref<SignalConfig>({
  type: 'sine',
  frequency: 10,
  amplitude: 100,
  phase: 0,
  dutyCycle: 0.5,
  pulseWidth: 0.01,
  sineComponents: [{ frequency: 10, amplitude: 100, phase: 0 }]
});

// 初始化信号配置
watch(() => props.modelValue, (newValue) => {
  signal.value = { 
    dutyCycle: 0.5, // 默认占空比
    pulseWidth: 0.01, // 默认脉冲宽度
    ...newValue 
  };
  if (!signal.value.sineComponents) {
    signal.value.sineComponents = [{ frequency: 10, amplitude: 100, phase: 0 }];
  }
}, { immediate: true });

// 监听信号变化并向上传递
watch(signal.value, (newSignal) => {
  emit('update:modelValue', newSignal);
}, { deep: true });

// 信号类型选项
const signalTypes = [
  { title: '正弦波', value: 'sine' },
  { title: '方波', value: 'square' },
  { title: '三角波', value: 'triangle' },
  { title: '脉冲', value: 'pulse' },
  { title: '多个正弦波叠加', value: 'multi_sine' }
];

// 获取信号图标
const getSignalIcon = (type: string) => {
  switch (type) {
    case 'sine': return 'mdi-sine-wave';
    case 'square': return 'mdi-square-wave';
    case 'triangle': return 'mdi-triangle-wave';
    case 'pulse': return 'mdi-pulse';
    case 'multi_sine': return 'mdi-chart-multiple';
    default: return 'mdi-waveform';
  }
};

// 预览信息
const previewInfo = computed(() => {
  const channelText = props.channelIndex !== undefined ? `通道 ${props.channelIndex + 1}: ` : '';
  
  switch (signal.value.type) {
    case 'sine':
      return `${channelText}正弦波 ${signal.value.frequency}Hz, 幅度 ${signal.value.amplitude}`;
    case 'square':
      return `${channelText}方波 ${signal.value.frequency}Hz, 占空比 ${(signal.value.dutyCycle || 0.5) * 100}%`;
    case 'triangle':
      return `${channelText}三角波 ${signal.value.frequency}Hz`;
    case 'pulse':
      return `${channelText}脉冲 ${signal.value.frequency}Hz, 宽度 ${signal.value.pulseWidth}s`;
    case 'multi_sine':
      return `${channelText}${signal.value.sineComponents?.length || 1}个正弦波叠加`;
    default:
      return `${channelText}${signal.value.type}信号`;
  }
});

// 添加正弦波分量
const addSineComponent = () => {
  if (!signal.value.sineComponents) {
    signal.value.sineComponents = [];
  }
  signal.value.sineComponents.push({
    frequency: 10,
    amplitude: 50,
    phase: 0
  });
};

// 移除正弦波分量
const removeSineComponent = (index: number) => {
  if (signal.value.sineComponents && signal.value.sineComponents.length > 1) {
    signal.value.sineComponents.splice(index, 1);
  }
};
</script>

<style scoped>
.signal-config-editor {
  min-width: 300px;
}
</style>