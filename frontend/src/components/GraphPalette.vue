<template>
  <div class="palette">
    <div class="palette-title">节点库</div>

    <div class="palette-body">
      <v-text-field
        v-model="search"
        label="搜索节点或设备"
        density="compact"
        variant="outlined"
        hide-details
        clearable
        prepend-inner-icon="mdi-magnify"
        class="palette-search"
      />

      <v-expansion-panels v-model="expanded" multiple variant="accordion" flat>
        <!-- 设备集合 -->
        <v-expansion-panel value="devices" :disabled="filteredDevices.length === 0 && !search">
          <v-expansion-panel-title class="group-title">
            <span>设备集合</span>
            <v-btn
              size="x-small"
              variant="text"
              color="primary"
              :disabled="!canEdit"
              @click.stop="$emit('createDevice')"
            >
              新建设备
            </v-btn>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="device in filteredDevices"
              :key="device.id"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEdit }"
              :draggable="canEdit"
              :title="canEdit ? `拖拽 ${device.port || device.name} 作为数据源节点` : '运行中不允许拖拽设备'"
              @dragstart="onDragStartDevice($event, device.id)"
            >
              <span class="item-icon" style="background: #e3f2fd; color: #1976d2;">DEV</span>
              <span class="item-name">{{ device.port || device.name }}</span>
            </div>
            <div v-if="filteredDevices.length === 0" class="palette-empty">
              {{ search ? '无匹配设备' : '暂无可用设备（请启动虚拟设备服务器）' }}
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <!-- 数据回放 -->
        <v-expansion-panel value="sources" :disabled="filteredSources.length === 0 && !search">
          <v-expansion-panel-title class="group-title">数据回放</v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredSources"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEdit }"
              :draggable="canEdit"
              :title="canEdit ? `${node.name} — ${node.desc}` : '运行中不允许添加节点'"
              @dragstart="onDragStart($event, node.type)"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <!-- 处理节点 -->
        <v-expansion-panel value="process" :disabled="filteredProcess.length === 0 && !search">
          <v-expansion-panel-title class="group-title">处理节点</v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredProcess"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEdit }"
              :draggable="canEdit"
              :title="canEdit ? `${node.name} — ${node.desc}` : '运行中不允许添加节点'"
              @dragstart="onDragStart($event, node.type)"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>

        <!-- 显示与保存 -->
        <v-expansion-panel value="output" :disabled="filteredOutput.length === 0 && !search">
          <v-expansion-panel-title class="group-title">显示与保存</v-expansion-panel-title>
          <v-expansion-panel-text>
            <div
              v-for="node in filteredOutput"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEdit }"
              :draggable="canEdit"
              :title="canEdit ? `${node.name} — ${node.desc}` : '运行中不允许添加节点'"
              @dragstart="onDragStart($event, node.type)"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { GraphNodeType } from '../services/graph';

interface PaletteDevice {
  id: string;
  name: string;
  status: string;
  port: string;
  type: string;
}

interface PaletteNode {
  type: GraphNodeType;
  name: string;
  icon: string;
  color: string;
  bg: string;
  desc: string;
}

const props = defineProps<{
  devices: PaletteDevice[];
  sourceNodes: PaletteNode[];
  processNodes: PaletteNode[];
  outputNodes: PaletteNode[];
  canEdit: boolean;
}>();

const emit = defineEmits<{
  (e: 'dragStart', type: GraphNodeType): void;
  (e: 'dragStartDevice', deviceId: string): void;
  (e: 'createDevice'): void;
}>();

const search = ref('');
const expanded = ref(['devices', 'sources', 'process', 'output']);

const matches = (text: string) => {
  if (!search.value) return true;
  return text.toLowerCase().includes(search.value.toLowerCase());
};

const filteredDevices = computed(() =>
  props.devices.filter((d) => matches(d.name) || matches(d.port) || matches(d.type))
);

const filteredSources = computed(() =>
  props.sourceNodes.filter((n) => matches(n.name) || matches(n.desc) || matches(n.type))
);

const filteredProcess = computed(() =>
  props.processNodes.filter((n) => matches(n.name) || matches(n.desc) || matches(n.type))
);

const filteredOutput = computed(() =>
  props.outputNodes.filter((n) => matches(n.name) || matches(n.desc) || matches(n.type))
);

function onDragStart(e: DragEvent, type: GraphNodeType) {
  if (!props.canEdit) {
    e.preventDefault();
    return;
  }
  emit('dragStart', type);
  e.dataTransfer?.setData('node-type', type);
  e.dataTransfer!.effectAllowed = 'copy';
}

function onDragStartDevice(e: DragEvent, deviceId: string) {
  if (!props.canEdit) {
    e.preventDefault();
    return;
  }
  emit('dragStartDevice', deviceId);
  e.dataTransfer?.setData('device-id', deviceId);
  e.dataTransfer!.effectAllowed = 'copy';
}
</script>

<style scoped>
.palette {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 240px;
  min-width: 240px;
  border-right: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  background-color: rgb(var(--v-theme-surface));
}

.palette-title {
  padding: 12px 14px;
  font-weight: 600;
  font-size: 15px;
  border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
  flex-shrink: 0;
}

.palette-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.palette-search {
  margin-bottom: 8px;
}

.group-title {
  font-weight: 500;
  font-size: 13px;
  padding: 0 8px;
  min-height: 36px;
}

.palette-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: grab;
  transition: background-color 0.18s ease;
}

.palette-item:hover {
  background-color: rgba(var(--v-theme-on-surface), 0.05);
}

.palette-item-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.item-icon {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-name {
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.palette-empty {
  padding: 12px 8px;
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.5);
  text-align: center;
}
</style>
