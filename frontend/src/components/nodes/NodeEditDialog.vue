<template>
  <v-dialog v-model="show" max-width="480" persistent>
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon :color="iconColor" class="mr-2">{{ icon }}</v-icon>
        编辑节点 - {{ nodeTypeName }}
        <v-spacer />
        <v-btn icon variant="text" size="small" @click="close">
          <v-icon>mdi-close</v-icon>
        </v-btn>
      </v-card-title>
      
      <v-divider />
      
      <v-card-text class="pt-4">
        <!-- 通用字段：名称 -->
        <v-text-field
          v-model="form.name"
          label="节点名称"
          density="compact"
          variant="outlined"
          class="mb-4"
        />
        
        <!-- 滤波器专用表单 -->
        <template v-if="nodeType === 'FILTER'">
          <v-select
            v-model="form.params.type"
            :items="['低通', '高通', '带通', '陷波']"
            label="滤波器类型"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="form.params.cutoff"
            label="截止频率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-slider
            v-model="form.params.order"
            :min="1"
            :max="8"
            :step="1"
            label="阶数"
            thumb-label
            class="mb-3"
          />
        </template>
        
        <!-- 数据源专用表单 -->
        <template v-else-if="nodeType === 'SOURCE'">
          <v-select
            v-model="form.params.device"
            :items="['模拟设备', '脑电设备-1', '脑电设备-2']"
            label="选择设备"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-text-field
            v-model.number="form.params.sampleRate"
            label="采样率 (Hz)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
        </template>
        
        <!-- 回放专用表单 -->
        <template v-else-if="nodeType === 'REPLAY'">
          <v-file-input
            v-model="form.params.file"
            label="选择数据文件"
            accept=".csv,.edf,.bdf"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-checkbox
            v-model="form.params.loop"
            label="循环播放"
            density="compact"
          />
        </template>
        
        <!-- 保存专用表单 -->
        <template v-else-if="nodeType === 'SAVE'">
          <v-text-field
            v-model="form.params.filename"
            label="文件名"
            density="compact"
            variant="outlined"
            class="mb-3"
            placeholder="data_YYYYMMDD.csv"
          />
          <v-select
            v-model="form.params.format"
            :items="['CSV', 'EDF', 'NPY']"
            label="保存格式"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
        </template>
        
        <!-- 示波器/频谱专用表单 -->
        <template v-else-if="['OSC', 'SPECTRUM'].includes(nodeType)">
          <v-text-field
            v-model.number="form.params.windowSize"
            label="窗口大小 (秒)"
            type="number"
            density="compact"
            variant="outlined"
            class="mb-3"
          />
          <v-select
            v-model="form.params.channels"
            :items="['全部通道', '1-4通道', '5-8通道']"
            label="显示通道"
            density="compact"
            variant="outlined"
          />
        </template>
        
        <!-- 分离器专用表单 -->
        <template v-else-if="nodeType === 'SPLIT'">
          <v-text-field
            v-model="form.params.groups"
            label="分组规则"
            density="compact"
            variant="outlined"
            class="mb-3"
            placeholder="1-4,5-8"
          />
        </template>
        
        <!-- 其他节点通用参数 -->
        <template v-else>
          <v-textarea
            v-model="paramsJson"
            label="参数 (JSON)"
            rows="4"
            density="compact"
            variant="outlined"
            :error="!!jsonError"
            :error-messages="jsonError"
          />
        </template>
      </v-card-text>
      
      <v-divider />
      
      <v-card-actions>
        <v-btn variant="text" @click="close">取消</v-btn>
        <v-spacer />
        <v-btn color="primary" @click="save">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

const props = defineProps<{
  modelValue: boolean;
  nodeData: {
    id: string;
    type: string;
    name: string;
    params: Record<string, any>;
  } | null;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', data: { name: string; params: Record<string, any> }): void;
}>();

const show = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
});

const nodeType = computed(() => props.nodeData?.type || '');

const typeInfo: Record<string, { name: string; icon: string; color: string }> = {
  SOURCE: { name: '数据源', icon: 'mdi-database', color: 'primary' },
  REPLAY: { name: '回放', icon: 'mdi-play-circle', color: 'primary' },
  FILTER: { name: '滤波器', icon: 'mdi-filter', color: 'success' },
  SUM: { name: '求和器', icon: 'mdi-plus-circle', color: 'purple' },
  SPLIT: { name: '分离器', icon: 'mdi-call-split', color: 'warning' },
  MERGE: { name: '合并器', icon: 'mdi-call-merge', color: 'orange' },
  OSC: { name: '示波器', icon: 'mdi-chart-line', color: 'teal' },
  SPECTRUM: { name: '频谱', icon: 'mdi-chart-bar', color: 'indigo' },
  SAVE: { name: '保存', icon: 'mdi-content-save', color: 'pink' },
};

const nodeTypeName = computed(() => typeInfo[nodeType.value]?.name || '节点');
const icon = computed(() => typeInfo[nodeType.value]?.icon || 'mdi-cube');
const iconColor = computed(() => typeInfo[nodeType.value]?.color || 'grey');

const form = ref({
  name: '',
  params: {} as Record<string, any>,
});

const paramsJson = ref('{}');
const jsonError = ref('');

watch(() => props.nodeData, (data) => {
  if (data) {
    form.value.name = data.name || '';
    form.value.params = { ...data.params };
    paramsJson.value = JSON.stringify(data.params || {}, null, 2);
    jsonError.value = '';
  }
}, { immediate: true });

watch(paramsJson, (val) => {
  try {
    form.value.params = JSON.parse(val);
    jsonError.value = '';
  } catch (e) {
    jsonError.value = 'JSON 格式错误';
  }
});

const close = () => {
  show.value = false;
};

const save = () => {
  if (jsonError.value) return;
  emit('save', {
    name: form.value.name,
    params: form.value.params,
  });
  close();
};
</script>
