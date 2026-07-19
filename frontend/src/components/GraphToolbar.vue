<template>
  <v-toolbar density="compact" color="surface" class="graph-toolbar">
    <v-toolbar-title class="d-flex align-center">
      <span>计算图编辑器</span>
      <v-chip
        v-if="isRunning"
        size="small"
        class="ml-3"
        color="warning"
      >
        <v-icon size="small" class="mr-1">mdi-play</v-icon>
        运行中
      </v-chip>
    </v-toolbar-title>

    <v-spacer />

    <div class="d-flex align-center ga-2">
      <!-- 同步状态 -->
      <v-tooltip v-if="showSyncChip" location="bottom">
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
import { shouldShowSyncChip } from '../services/uiLogic';

type SyncStatus = 'idle' | 'saving' | 'ok' | 'error';

const props = defineProps<{
  isRunning: boolean;
  canEdit: boolean;
  syncStatus: SyncStatus;
  syncError?: string;
}>();

const emit = defineEmits<{
  (e: 'save'): void;
  (e: 'export'): void;
  (e: 'load'): void;
  (e: 'clear'): void;
  (e: 'openDeviceManager'): void;
  (e: 'retrySync'): void;
}>();

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

// 运行时隐藏 idle 状态的「编辑中」chip（标题栏已有「运行中」标识）
const showSyncChip = computed(() => shouldShowSyncChip(props.isRunning, props.syncStatus));
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
