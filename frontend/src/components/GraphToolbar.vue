<template>
  <v-toolbar density="compact" color="surface" class="graph-toolbar">
    <v-toolbar-title class="d-flex align-center">
      <span>计算图编辑器</span>
      <v-chip
        v-if="isRunning || frozen"
        size="small"
        class="ml-3"
        :color="isRunning ? 'warning' : 'info'"
      >
        <v-icon size="small" class="mr-1">
          {{ isRunning ? 'mdi-play' : 'mdi-lock' }}
        </v-icon>
        {{ isRunning ? '运行中' : '已冻结' }}
      </v-chip>
    </v-toolbar-title>

    <v-spacer />

    <div class="d-flex align-center ga-2">
      <!-- 冻结/编辑开关 -->
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-switch
            v-bind="props"
            :model-value="frozen"
            :disabled="isRunning"
            hide-details
            density="compact"
            color="primary"
            :label="frozen ? '已冻结' : '编辑中'"
            class="freeze-switch"
            @update:model-value="onFreezeChange"
          />
        </template>
        <span>{{ frozen ? '解冻后可编辑计算图' : '冻结后启用运行/可视化' }}</span>
      </v-tooltip>

      <!-- 同步状态 -->
      <v-tooltip location="bottom">
        <template #activator="{ props }">
          <v-chip
            v-bind="props"
            size="small"
            :color="syncChip.color"
            :variant="syncStatus === 'error' ? 'tonal' : 'flat'"
            :class="{ 'cursor-pointer': syncStatus === 'error' }"
            @click="syncStatus === 'error' ? $emit('retrySync') : undefined"
          >
            <v-icon size="small" class="mr-1">{{ syncChip.icon }}</v-icon>
            {{ syncChip.text }}
          </v-chip>
        </template>
        <span>{{ syncStatus === 'error' ? syncError || '点击重试' : '计算图同步状态' }}</span>
      </v-tooltip>

      <v-divider vertical class="mx-1" />

      <!-- 文件操作 -->
      <v-btn
        size="small"
        variant="tonal"
        prepend-icon="mdi-content-save"
        :disabled="isRunning || !canEdit"
        @click="$emit('save')"
      >
        保存
      </v-btn>
      <v-btn
        size="small"
        variant="tonal"
        prepend-icon="mdi-download"
        @click="$emit('export')"
      >
        导出
      </v-btn>
      <v-btn
        size="small"
        variant="tonal"
        prepend-icon="mdi-upload"
        :disabled="isRunning || !canEdit"
        @click="$emit('load')"
      >
        加载
      </v-btn>
      <v-btn
        size="small"
        color="info"
        variant="tonal"
        prepend-icon="mdi-eraser"
        :disabled="isRunning || !canEdit"
        @click="$emit('clear')"
      >
        清空
      </v-btn>

      <v-divider vertical class="mx-1" />

      <!-- 端口颜色图例 -->
      <div class="d-flex align-center ga-1 legend">
        <span class="text-caption port-legend-in">● 输入</span>
        <span class="text-caption port-legend-out">● 输出</span>
      </div>

      <!-- 设备管理 -->
      <v-btn
        size="small"
        variant="tonal"
        prepend-icon="mdi-devices"
        @click="$emit('openDeviceManager')"
      >
        设备管理
      </v-btn>
    </div>
  </v-toolbar>
</template>

<script setup lang="ts">
import { computed } from 'vue';

type SyncStatus = 'idle' | 'saving' | 'ok' | 'error';

const props = defineProps<{
  isRunning: boolean;
  frozen: boolean;
  canEdit: boolean;
  syncStatus: SyncStatus;
  syncError?: string;
}>();

const emit = defineEmits<{
  (e: 'freeze', value: boolean): void;
  (e: 'save'): void;
  (e: 'export'): void;
  (e: 'load'): void;
  (e: 'clear'): void;
  (e: 'openDeviceManager'): void;
  (e: 'retrySync'): void;
}>();

function onFreezeChange(value: boolean | null) {
  emit('freeze', Boolean(value));
}

const syncChip = computed(() => {
  switch (props.syncStatus) {
    case 'saving':
      return { icon: 'mdi-cloud-upload', text: '同步中…', color: 'primary' };
    case 'ok':
      return { icon: 'mdi-check-circle', text: '已同步', color: 'success' };
    case 'error':
      return { icon: 'mdi-alert-circle', text: props.syncError || '同步失败', color: 'error' };
    default:
      return { icon: 'mdi-pencil', text: '编辑中', color: 'default' };
  }
});
</script>

<style scoped>
.graph-toolbar {
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.freeze-switch {
  margin-top: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.legend {
  user-select: none;
}

.port-legend-in {
  color: #e53935;
}

.port-legend-out {
  color: #43a047;
}
</style>
