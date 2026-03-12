<template>
  <div class="fullscreen-graph-editor">
    <v-toolbar density="compact" color="surface" class="graph-toolbar">
      <v-toolbar-title>计算图编辑器</v-toolbar-title>
      <v-spacer />
      <div class="d-flex align-center ga-2">
        <!-- 状态提示 -->
        <v-chip size="small" :color="isRunning ? 'warning' : (frozen ? 'info' : 'default')">
          <v-icon size="small" class="mr-1">
            {{ isRunning ? 'mdi-play' : (frozen ? 'mdi-lock' : 'mdi-pencil') }}
          </v-icon>
          {{ statusDescription }}
        </v-chip>

        <v-chip v-if="hasUnsavedChanges" size="small" color="warning" variant="tonal">
          <v-icon size="small" class="mr-1">mdi-content-save-alert</v-icon>
          有未保存更改
        </v-chip>

        <v-btn
          size="small"
          color="primary"
          variant="flat"
          @click="save"
          :disabled="!canEditGraphLocal || !hasUnsavedChanges"
          :title="!canEditGraphLocal ? `当前状态不允许保存: ${statusDescription}` : (hasUnsavedChanges ? '保存到后端 (Ctrl+S)' : '当前无未保存更改')"
        >
          保存
        </v-btn>
        
        <v-btn size="small" variant="tonal" @click="exportGraph">导出</v-btn>
        <v-btn 
          size="small" 
          variant="tonal" 
          @click="triggerFileLoad"
          :disabled="!canEditGraphLocal"
          :title="!canEditGraphLocal ? `当前状态不允许加载计算图: ${statusDescription}` : '从文件加载计算图'"
        >
          加载
        </v-btn>
        <v-btn 
          size="small" 
          color="secondary" 
          @click="loadMockData"
          :disabled="!canEditGraphLocal"
          :title="!canEditGraphLocal ? `当前状态不允许加载Mock数据: ${statusDescription}` : '加载Mock数据'"
        >
          加载Mock
        </v-btn>
        <v-btn 
          size="small" 
          color="info" 
          @click="clear"
          :disabled="!canEditGraphLocal"
          :title="!canEditGraphLocal ? `当前状态不允许清空计算图: ${statusDescription}` : '清空计算图'"
        >
          清空
        </v-btn>
      </div>
    </v-toolbar>

    <div class="graph-content">

      <div class="graph-wrapper">
        <!-- 左侧节点库 -->
        <div class="palette">
          <div class="palette-title">节点库</div>

          <div class="palette-group">
            <div class="group-title">数据来源</div>
            <div
              v-for="node in sourceNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `当前状态不允许添加节点: ${statusDescription}` : `添加 ${node.name} 节点`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>

          <div class="palette-group">
            <div class="group-title">处理节点</div>
            <div
              v-for="node in processNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `当前状态不允许添加节点: ${statusDescription}` : `添加 ${node.name} 节点`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>

          <div class="palette-group">
            <div class="group-title">显示与保存</div>
            <div
              v-for="node in outputNodes"
              :key="node.type"
              class="palette-item"
              :class="{ 'palette-item-disabled': !canEditGraphLocal }"
              :draggable="canEditGraphLocal"
              @dragstart="onDragStart($event, node.type)"
              :title="!canEditGraphLocal ? `当前状态不允许添加节点: ${statusDescription}` : `添加 ${node.name} 节点`"
            >
              <span class="item-icon" :style="{ background: node.bg, color: node.color }">
                {{ node.icon }}
              </span>
              <span class="item-name">{{ node.name }}</span>
            </div>
          </div>
        </div>

        <!-- 右侧画布 -->
        <div ref="container" class="graph-container">
          <div v-if="!hasNodes" class="graph-hint">
            <v-icon size="48" color="grey-lighten-2">mdi-graph-outline</v-icon>
            <div class="hint-text">从左侧拖拽节点到此处</div>
            <div class="hint-sub">双击节点可编辑参数<br>连接节点创建数据处理流程</div>
          </div>
        </div>

        <!-- 右侧编辑边栏 -->
        <div class="sidebar" :class="{ 'sidebar-collapsed': !sidebarExpanded }">
          <!-- 边栏头部：折叠按钮和标题 -->
          <div class="sidebar-header">
            <v-btn
              icon
              size="small"
              variant="text"
              @click="sidebarExpanded = !sidebarExpanded"
              class="sidebar-toggle"
            >
              <v-icon v-if="sidebarExpanded">mdi-chevron-right</v-icon>
              <v-icon v-else>mdi-chevron-left</v-icon>
            </v-btn>
            <div v-if="sidebarExpanded" class="sidebar-title">
              <v-icon :color="sidebarIconColor" class="mr-2">{{ sidebarIcon }}</v-icon>
              {{ sidebarTitle }}
            </div>
          </div>

          <!-- 边栏内容 -->
          <div v-if="sidebarExpanded" class="sidebar-content">
            <!-- 节点编辑内容 -->
            <NodeEditDialog
              v-model="nodeEditDialogOpen"
              :node-data="editingNode"
              :all-nodes="allNodes"
              :all-edges="allEdges"
              mode="sidebar"
              @save="handleNodeSave"
              @bindOscilloscope="handleBindOscilloscope"
              class="sidebar-node-edit"
            />
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- 节点编辑对话框 -->
  <v-dialog v-model="editDialog.open" max-width="500">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" :color="editDialog.config?.color">mdi-cog</v-icon>
        {{ frozen ? '查看节点' : '编辑节点' }}: {{ editDialog.nodeName }}
      </v-card-title>
      <v-divider />
      <v-card-text class="pt-4">
        <!-- 节点名称 -->
        <v-text-field
          v-model="editDialog.nodeName"
          label="节点名称"
          variant="outlined"
          density="compact"
          class="mb-4"
          :readonly="frozen"
          :disabled="frozen"
        />

        <!-- 动态参数表单 -->
        <div v-for="field in editDialog.fields" :key="field.key" class="mb-3">
          <!-- 数字输入 -->
          <v-text-field
            v-if="field.type === 'number'"
            v-model.number="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            type="number"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 文本输入 -->
          <v-text-field
            v-else-if="field.type === 'text'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 选择器 -->
          <v-select
            v-else-if="field.type === 'select'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :items="field.options"
            :hint="field.hint"
            variant="outlined"
            density="compact"
            persistent-hint
            :readonly="frozen"
            :disabled="frozen"
          />

          <!-- 滑块 -->
          <div v-else-if="field.type === 'slider'">
            <div class="d-flex align-center justify-space-between mb-1">
              <span class="text-body-2">{{ field.label }}</span>
              <span class="text-caption text-grey">{{ editDialog.params[field.key] }}</span>
            </div>
            <v-slider
              v-model.number="editDialog.params[field.key]"
              :min="field.min"
              :max="field.max"
              :step="field.step || 1"
              density="compact"
              hide-details
              :readonly="frozen"
              :disabled="frozen"
            />
            <div class="text-caption text-grey mt-1">{{ field.hint }}</div>
          </div>

          <!-- 开关 -->
          <v-switch
            v-else-if="field.type === 'boolean'"
            v-model="editDialog.params[field.key]"
            :label="field.label"
            :hint="field.hint"
            density="compact"
            hide-details
            :readonly="frozen"
            :disabled="frozen"
          />
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="editDialog.open = false">{{ frozen ? '关闭' : '取消' }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 隐藏的文件输入用于加载计算图 -->
  <input
    id="graph-file-input"
    type="file"
    accept=".json"
    style="display: none"
    @change="loadGraphFromFile"
  />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick, watch, computed } from 'vue';
import { onBeforeRouteLeave } from 'vue-router';
import { Graph, Snapline } from '@antv/x6';
import {
  fetchGraph,
  saveGraph,
  type GraphNode,
  type GraphNodeType,
  type GraphPayload,
} from '../services/graph';
import { graphRuntime, type EegPacket } from '../services/runtime';
import { sessionStore } from '../services/sessionStore';
import { eegWebSocket } from '../services/websocket';
import { graphRuntimeStore } from '../services/graphRuntimeStore';
import { graphSyncWebSocket } from '../services/graphSyncWebSocket';

import NodeEditDialog from './nodes/NodeEditDialog.vue';

// 会话存储键名
const SESSION_STORAGE_KEY = 'eeg_graph_editor_state';

const container = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const hasNodes = ref(false);
const hasUnsavedChanges = ref(false);
const isApplyingBackendGraph = ref(false);
const lastSyncedSignature = ref('');

function sortValueDeep(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => sortValueDeep(item));
  }
  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, val]) => [key, sortValueDeep(val)]);
    return Object.fromEntries(entries);
  }
  return value;
}

function payloadSignature(payload: GraphPayload): string {
  const normalized: GraphPayload = {
    frozen: Boolean(payload.frozen),
    nodes: [...(payload.nodes || [])]
      .map((node) => sortValueDeep(node) as GraphNode)
      .sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''))),
    edges: [...(payload.edges || [])]
      .map((edge) => sortValueDeep(edge) as typeof payload.edges[number])
      .sort((a, b) => String(a.id || '').localeCompare(String(b.id || ''))),
  };
  return JSON.stringify(normalized);
}

function syncUnsavedState() {
  if (isApplyingBackendGraph.value) return;
  const current = buildPayload();
  hasUnsavedChanges.value = payloadSignature(current) !== lastSyncedSignature.value;
}

// 从全局状态管理获取状态
const {
  isRunning,
  runtimeMode,
  frozen,
  offlineProgress,
  processingDelayMs,
  nonRealtime,
  runtimeWarning,
  canEditGraph,
  canRunGraph,
  statusDescription
} = graphRuntimeStore;

const setRuntimeState = (patch: Record<string, unknown>) => {
  graphRuntimeStore.updateState(patch as any);
};

async function pollRuntimeState() {
  await graphRuntimeStore.pollRuntimeState();
}

function startRuntimeStatePolling() {
  graphRuntimeStore.startPolling();
}

function stopRuntimeStatePolling() {
  graphRuntimeStore.stopPolling();
}

// 右侧边栏状态
const sidebarExpanded = ref(true);
const selectedNodeId = ref<string | null>(null);

// 计算属性：边栏标题、图标和颜色
const sidebarTitle = computed(() => {
  if (!editingNode.value) return '节点编辑';
  const typeInfo = nodeTypes[editingNode.value.type];
  return `${typeInfo?.name || '节点'} - ${editingNode.value.name || '未命名'}`;
});

const sidebarIcon = computed(() => {
  if (!editingNode.value) return 'mdi-cog';
  const typeInfo = nodeTypes[editingNode.value.type];
  return typeInfo?.icon || 'mdi-cog';
});

const sidebarIconColor = computed(() => {
  if (!editingNode.value) return 'primary';
  const typeInfo = nodeTypes[editingNode.value.type];
  return typeInfo?.color || 'primary';
});

// 计算属性：检查是否允许编辑计算图（结合全局状态和会话状态）
const canEditGraphLocal = computed(() => {
  return sessionStore.canEditGraph() && !isRunning.value;
});

let edgeAnimationTimer: number | null = null;
const edgeAnimationStates = ref<Map<string, { active: boolean; progress: number }>>(new Map());

// 边动画管理
function startEdgeAnimations() {
  if (edgeAnimationTimer) return;
  
  edgeAnimationTimer = window.setInterval(() => {
    const graph = graphRef.value;
    if (!graph || !isRunning.value) return;
    
    // 更新所有边的动画状态
    graph.getEdges().forEach((edge) => {
      const edgeId = edge.id;
      const currentState = edgeAnimationStates.value.get(edgeId) || { active: false, progress: 0 };
      
      // 根据运行状态决定动画类型
      const shouldBeActive = isRunning.value;
      const isLiveMode = runtimeMode.value === 'live';
      
      if (shouldBeActive !== currentState.active) {
        currentState.active = shouldBeActive;
        currentState.progress = 0;
        edgeAnimationStates.value.set(edgeId, currentState);
      }
      
      if (currentState.active) {
        // 更新动画进度
        currentState.progress = (currentState.progress + (isLiveMode ? 0.05 : 0.02)) % 1;
        edgeAnimationStates.value.set(edgeId, currentState);
        
        // 应用动画效果
        if (isLiveMode) {
          applyLiveEdgeAnimation(edge, currentState.progress);
        } else {
          applyOfflineEdgeAnimation(edge, currentState.progress);
        }
      } else {
        // 清除动画效果
        clearEdgeAnimation(edge);
      }
    });
  }, 50); // 20fps 动画
}

function stopEdgeAnimations() {
  if (edgeAnimationTimer) {
    clearInterval(edgeAnimationTimer);
    edgeAnimationTimer = null;
  }
  
  // 清除所有边的动画效果
  const graph = graphRef.value;
  if (graph) {
    graph.getEdges().forEach((edge) => {
      clearEdgeAnimation(edge);
    });
  }
  
  edgeAnimationStates.value.clear();
}

function applyLiveEdgeAnimation(edge: import('@antv/x6').Edge, progress: number) {
  // Live模式：快速流动动画效果
  const strokeDasharray = '10, 5';
  const strokeDashoffset = -progress * 15; // 流动效果
  
  edge.attr({
    line: {
      strokeDasharray,
      strokeDashoffset,
      stroke: '#5F95FF',
      strokeWidth: 2,
      style: {
        animation: 'none',
      },
    },
    sourceMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
    targetMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
  });
  
  // 添加发光效果
  edge.addTools({
    name: 'segments',
    args: {
      snapRadius: 20,
      attrs: {
        fill: '#5F95FF',
        stroke: '#5F95FF',
        'stroke-width': 4,
        opacity: 0.3,
      },
    },
  });
}

function applyOfflineEdgeAnimation(edge: import('@antv/x6').Edge, progress: number) {
  // 离线模式：缓慢脉冲动画效果
  const pulseIntensity = 0.5 + 0.5 * Math.sin(progress * Math.PI * 2);
  const strokeWidth = 1 + pulseIntensity; // 1-2px 脉动
  
  edge.attr({
    line: {
      stroke: '#9C27B0', // 紫色表示离线处理
      strokeWidth,
      strokeDasharray: '5, 3',
      strokeDashoffset: -progress * 8,
    },
    sourceMarker: {
      fill: '#9C27B0',
      stroke: '#9C27B0',
    },
    targetMarker: {
      fill: '#9C27B0',
      stroke: '#9C27B0',
    },
  });
  
  // 添加脉冲效果
  edge.addTools({
    name: 'segments',
    args: {
      snapRadius: 20,
      attrs: {
        fill: '#9C27B0',
        stroke: '#9C27B0',
        'stroke-width': 2 + pulseIntensity * 2,
        opacity: 0.2 + pulseIntensity * 0.2,
      },
    },
  });
}

function clearEdgeAnimation(edge: import('@antv/x6').Edge) {
  edge.attr({
    line: {
      strokeDasharray: '',
      strokeDashoffset: 0,
      stroke: '#5F95FF',
      strokeWidth: 2,
    },
    sourceMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
    targetMarker: {
      fill: '#5F95FF',
      stroke: '#5F95FF',
    },
  });
  
  // 移除工具
  edge.removeTools();
}

// 停止运行函数（用于边动画管理）
async function stopRunLocal() {
  try {
    graphRuntime.stop();
    stopMockDataStream();
    
    // 停止边动画
    stopEdgeAnimations();
    
    console.log('[GraphEditor] Graph stopped locally');
    
    // 保存状态到会话存储
    saveStateToSessionStorage();
  } catch (err) {
    console.error('[GraphEditor] Failed to stop graph locally:', err);
  }
}

// 存储 sessionStore 取消订阅函数
let unsubscribeSessionStore: (() => void) | null = null;
let unsubscribeGraphSync: (() => void) | null = null;

function onSaveHotkey(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey)) return;
  if (event.key.toLowerCase() !== 's') return;
  event.preventDefault();
  if (!canEditGraphLocal.value || !hasUnsavedChanges.value) return;
  void save();
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!hasUnsavedChanges.value) return;
  event.preventDefault();
  event.returnValue = '';
}

onBeforeRouteLeave((_to, _from, next) => {
  if (!hasUnsavedChanges.value) {
    next();
    return;
  }
  const confirmed = window.confirm('当前计算图有未保存更改，离开后将丢失。是否继续离开？');
  next(confirmed);
});

// 新增：NodeEditDialog 相关状态
const nodeEditDialogOpen = ref(false);
const editingNode = ref<GraphNode | null>(null);
const allNodes = ref<GraphNode[]>([]);
const allEdges = ref<Array<{id: string; source: string; target: string; sourcePort?: string; targetPort?: string}>>([]);

// 节点编辑对话框状态
const editDialog = ref({
  open: false,
  nodeId: '',
  nodeName: '',
  nodeType: '' as GraphNodeType | '',
  params: {} as Record<string, unknown>,
  config: null as { color: string; bg: string } | null,
  fields: [] as ParamField[],
});

// 监听冻结状态变化
let isInitializing = true;
watch(frozen, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    console.log(`[GraphEditor] Frozen state changed: ${oldVal} -> ${newVal}`);
    
    // 初始化时不自动触发冻结操作
    if (!isInitializing) {
      applyFrozen();
    }
  }
});

// 在计算图加载完成后设置初始化完成
onMounted(() => {
  // 延迟设置，确保计算图已加载
  setTimeout(() => {
    isInitializing = false;
    console.log('[GraphEditor] Initialization complete, frozen watcher enabled');
  }, 1000);
});

// 保存节点编辑（旧版，保留兼容性）
function saveNodeEdit() {
  // 冻结状态下禁止编辑
  if (frozen.value) {
    console.log('[GraphEditor] 冻结状态下禁止编辑节点');
    return;
  }
  
  const graph = graphRef.value;
  if (!graph || !editDialog.value.nodeId) return;

  const node = graph.getCellById(editDialog.value.nodeId);
  if (!node || !node.isNode()) return;

  // 更新节点数据
  const data = node.getData() as GraphNode;
  data.name = editDialog.value.nodeName;
  data.params = { ...editDialog.value.params };
  node.setData(data);

  // 更新节点标签显示
  const labelText = generateNodeLabel(data.type, data.name, data.params, editDialog.value.nodeId);
  node.attr('label/text', labelText);

  editDialog.value.open = false;
}

// 防抖保存函数（用于旧版对话框）
let debounceSaveTimeout: number | null = null;
const debouncedSaveNodeEdit = () => {
  if (debounceSaveTimeout) {
    clearTimeout(debounceSaveTimeout);
  }
  debounceSaveTimeout = setTimeout(() => {
    if (editDialog.value.open && editDialog.value.nodeId && !frozen.value) {
      saveNodeEdit();
    }
  }, 500); // 500ms防抖
};

// 监听编辑对话框变化，自动保存
watch(() => editDialog.value, (newVal, oldVal) => {
  if (!newVal.open || frozen.value) return;
  
  // 检查是否有实际变化
  const hasNameChanged = newVal.nodeName !== oldVal?.nodeName;
  const hasParamsChanged = JSON.stringify(newVal.params) !== JSON.stringify(oldVal?.params);
  
  if (hasNameChanged || hasParamsChanged) {
    debouncedSaveNodeEdit();
  }
}, { deep: true });

// 参数字段定义
interface ParamField {
  key: string;
  label: string;
  type: 'number' | 'text' | 'select' | 'slider' | 'boolean';
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  default?: unknown;
}

// 各节点类型的参数配置
const nodeParamConfigs: Record<GraphNodeType, ParamField[]> = {
  SOURCE: [
    { key: 'sampleRate', label: '采样率', type: 'number', hint: 'Hz', default: 1000 },
    { key: 'channels', label: '通道数', type: 'slider', min: 1, max: 32, hint: '通道数量', default: 8 },
    { key: 'deviceId', label: '设备ID', type: 'text', hint: '脑电设备标识', default: 'sim-001' },
  ],
  REPLAY: [
    { key: 'filePath', label: '数据文件', type: 'text', hint: '回放文件路径', default: '' },
    { key: 'speed', label: '播放速度', type: 'slider', min: 0.5, max: 5, step: 0.5, hint: '倍速播放', default: 1 },
    { key: 'loop', label: '循环播放', type: 'boolean', hint: '是否循环', default: false },
  ],
  FILTER: [
    { key: 'type', label: '滤波器类型', type: 'select', options: ['lowpass', 'highpass', 'bandpass', 'notch'], hint: '滤波类型', default: 'lowpass' },
    { key: 'cutoff', label: '截止频率', type: 'number', hint: 'Hz', default: 50 },
    { key: 'order', label: '阶数', type: 'slider', min: 1, max: 8, hint: '滤波器阶数', default: 4 },
  ],
  DOWNSAMPLE: [
    { key: 'mode', label: '模式', type: 'select', options: ['targetRate', 'factor'], hint: '目标频率或倍率', default: 'targetRate' },
    { key: 'targetRate', label: '目标频率', type: 'number', hint: 'Hz', default: 250 },
    { key: 'factor', label: '降采样倍率', type: 'number', hint: 'factor>=1', default: 2 },
  ],
  UPSAMPLE: [
    { key: 'mode', label: '模式', type: 'select', options: ['targetRate', 'factor'], hint: '目标频率或倍率', default: 'targetRate' },
    { key: 'targetRate', label: '目标频率', type: 'number', hint: 'Hz', default: 1000 },
    { key: 'factor', label: '升采样倍率', type: 'number', hint: 'factor>=1', default: 2 },
  ],
  SUM: [
    { key: 'inputs', label: '输入配置', type: 'text', hint: '每个输入独立权重', default: [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }] },
  ],
  SPLIT: [
    { key: 'outputs', label: '输出配置', type: 'text', hint: '每个输出独立通道配置', default: [{ label: '输出1', channelIndices: '0,1,2,3' }] },
  ],
  MERGE: [
    { key: 'inputs', label: '输入配置', type: 'text', hint: '每个输入独立增益', default: [{ label: '输入1', gain: 1 }, { label: '输入2', gain: 1 }] },
    { key: 'strategy', label: '合并策略', type: 'select', options: ['interleave', 'concatenate'], hint: '数据合并方式', default: 'interleave' },
  ],
  OSC: [
    { key: 'timeWindow', label: '时间窗口', type: 'slider', min: 1, max: 15, hint: '秒', default: 5 },
    { key: 'yScale', label: 'Y轴缩放', type: 'slider', min: 0.2, max: 5, step: 0.1, hint: '波形显示缩放', default: 1 },
    { key: 'mode', label: '显示模式', type: 'select', options: ['scroll', 'scan'], hint: '滚动或扫描', default: 'scroll' },
  ],
  SPECTRUM: [
    { key: 'fftSize', label: 'FFT点数', type: 'select', options: ['256', '512', '1024', '2048'], hint: 'FFT窗口大小', default: '1024' },
    { key: 'overlap', label: '重叠率', type: 'slider', min: 0, max: 0.9, step: 0.1, hint: '窗口重叠比例', default: 0.5 },
  ],
  SAVE: [
    { key: 'format', label: '保存格式', type: 'select', options: ['edf', 'csv', 'json'], hint: '文件格式', default: 'edf' },
    { key: 'filePath', label: '保存路径', type: 'text', hint: '文件保存路径', default: './data/output.edf' },
    { key: 'bufferSize', label: '缓冲区大小', type: 'number', hint: '样本数', default: 10000 },
  ],
  CUSTOM_PYFUNC: [
    { key: 'portMode', label: '端口模式', type: 'select', options: ['fixed', 'adaptive'], hint: 'fixed=固定数量，adaptive=自适应', default: 'fixed' },
    { key: 'inputCount', label: '输入数量', type: 'number', hint: '固定模式生效', default: 2 },
    { key: 'outputCount', label: '输出数量', type: 'number', hint: '固定模式生效', default: 1 },
    { key: 'hopMode', label: '滑动间隔模式', type: 'select', options: ['points', 'milliseconds', 'targetRate'], hint: '决定输出频率', default: 'points' },
    { key: 'hopPoints', label: '滑动点数', type: 'number', hint: 'points模式', default: 1 },
    { key: 'hopMs', label: '滑动毫秒', type: 'number', hint: 'milliseconds模式', default: 10 },
    { key: 'outputSampleRate', label: '目标输出频率', type: 'number', hint: 'targetRate模式', default: 100 },
  ],
  CUSTOM_CONV: [
    { key: 'kernel', label: '卷积核', type: 'text', hint: '例如: 0.25,0.5,0.25', default: '0.25,0.5,0.25' },
  ],
};

// 节点类型配置
const nodeTypes: Record<GraphNodeType, { name: string; color: string; bg: string; icon: string; hasInput: boolean; hasOutput: boolean }> = {
  SOURCE: { name: '数据源', color: '#1976D2', bg: '#E3F2FD', icon: 'SRC', hasInput: false, hasOutput: true },
  REPLAY: { name: '回放', color: '#1976D2', bg: '#E3F2FD', icon: 'RPL', hasInput: false, hasOutput: true },
  FILTER: { name: '滤波器', color: '#388E3C', bg: '#E8F5E9', icon: 'FIL', hasInput: true, hasOutput: true },
  DOWNSAMPLE: { name: '降采样', color: '#6D4C41', bg: '#EFEBE9', icon: 'DS', hasInput: true, hasOutput: true },
  UPSAMPLE: { name: '升采样', color: '#455A64', bg: '#ECEFF1', icon: 'US', hasInput: true, hasOutput: true },
  SUM: { name: '求和器', color: '#7B1FA2', bg: '#F3E5F5', icon: 'SUM', hasInput: true, hasOutput: true },
  SPLIT: { name: '分离器', color: '#F9A825', bg: '#FFF8E1', icon: 'SPT', hasInput: true, hasOutput: true },
  MERGE: { name: '合并器', color: '#EF6C00', bg: '#FFF3E0', icon: 'MRG', hasInput: true, hasOutput: true },
  OSC: { name: '示波器', color: '#00796B', bg: '#E0F2F1', icon: 'OSC', hasInput: true, hasOutput: false },
  SPECTRUM: { name: '频谱', color: '#3F51B5', bg: '#E8EAF6', icon: 'FFT', hasInput: true, hasOutput: false },
  SAVE: { name: '保存', color: '#C2185B', bg: '#FCE4EC', icon: 'SAV', hasInput: true, hasOutput: false },
  CUSTOM_PYFUNC: { name: 'Python函数', color: '#5E35B1', bg: '#EDE7F6', icon: 'PY', hasInput: true, hasOutput: true },
  CUSTOM_CONV: { name: '卷积节点', color: '#00897B', bg: '#E0F2F1', icon: 'CNV', hasInput: true, hasOutput: true },
};

const sourceNodes = [
  { type: 'SOURCE' as GraphNodeType, name: '数据源', icon: 'SRC', color: '#1976D2', bg: '#E3F2FD' },
];

const processNodes = [
  { type: 'FILTER' as GraphNodeType, name: '滤波器', icon: 'FIL', color: '#388E3C', bg: '#E8F5E9' },
  { type: 'DOWNSAMPLE' as GraphNodeType, name: '降采样', icon: 'DS', color: '#6D4C41', bg: '#EFEBE9' },
  { type: 'UPSAMPLE' as GraphNodeType, name: '升采样', icon: 'US', color: '#455A64', bg: '#ECEFF1' },
  { type: 'SUM' as GraphNodeType, name: '求和器', icon: 'SUM', color: '#7B1FA2', bg: '#F3E5F5' },
  { type: 'SPLIT' as GraphNodeType, name: '分离器', icon: 'SPT', color: '#F9A825', bg: '#FFF8E1' },
  { type: 'MERGE' as GraphNodeType, name: '合并器', icon: 'MRG', color: '#EF6C00', bg: '#FFF3E0' },
  { type: 'CUSTOM_PYFUNC' as GraphNodeType, name: 'Python函数', icon: 'PY', color: '#5E35B1', bg: '#EDE7F6' },
  { type: 'CUSTOM_CONV' as GraphNodeType, name: '卷积节点', icon: 'CNV', color: '#00897B', bg: '#E0F2F1' },
];

const outputNodes = [
  { type: 'OSC' as GraphNodeType, name: '示波器', icon: 'OSC', color: '#00796B', bg: '#E0F2F1' },
  { type: 'SPECTRUM' as GraphNodeType, name: '频谱', icon: 'FFT', color: '#3F51B5', bg: '#E8EAF6' },
];

// 选择节点并在右侧边栏显示
function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId;
  openNodeEditDialog(nodeId);
}

// 打开节点编辑对话框
function openNodeEditDialog(nodeId: string) {
  const graph = graphRef.value;
  if (!graph) return;

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return;

  const data = node.getData() as GraphNode;
  const { x, y } = node.position();

  // 更新所有节点和边的信息
  allNodes.value = graph.getNodes().map((n) => {
    const nodeData = n.getData() as GraphNode;
    const pos = n.position();
    return { ...nodeData, id: n.id, x: pos.x, y: pos.y };
  });
  allEdges.value = graph.getEdges().map((e) => ({
    id: e.id,
    source: e.getSourceCellId() || '',
    target: e.getTargetCellId() || '',
    sourcePort: e.getSourcePortId() || undefined,
    targetPort: e.getTargetPortId() || undefined,
  }));

  // 更新编辑节点数据
  editingNode.value = { ...data, id: nodeId, x, y };
  // 传递冻结状态给对话框
  editingNode.value.frozen = frozen.value;
  // 在右侧边栏中显示节点编辑内容
  // nodeEditDialogOpen.value = true; // 不再需要，因为内容直接显示在边栏中
}

// 处理节点保存
async function handleNodeSave({ name, params, deviceId }: { name: string; params: Record<string, unknown>; deviceId?: string | null }) {
  // 检查编辑权限
  if (!canEditGraphLocal.value) {
    console.log(`[GraphEditor] 当前状态不允许保存节点: ${statusDescription.value}`);
    alert(`当前状态不允许保存节点: ${statusDescription.value}`);
    return;
  }
  
  const graph = graphRef.value;
  if (!graph || !editingNode.value) return;

  const node = graph.getCellById(editingNode.value.id);
  if (!node || !node.isNode()) return;

  // 更新节点数据
  const data = node.getData() as GraphNode;
  data.name = name;
  data.params = normalizeNodeParams(data.type, { ...params });
  if (deviceId !== undefined) {
    data.deviceId = deviceId || undefined;
  }
  node.setData(data);

  // 根据配置刷新动态端口
  syncNodePorts(node, data.type, data.params);

  // 参数变化后刷新边标签
  updateAllEdgeLabels();

  // 更新节点标签显示
  const labelText = generateNodeLabel(data.type, data.name, data.params, editingNode.value?.id);
  node.attr('label/text', labelText);

  syncUnsavedState();
}

// 处理示波器绑定
function handleBindOscilloscope({ nodeId, oscId }: { nodeId: string; oscId: string | null }) {
  // 冻结状态下禁止绑定/解绑
  if (frozen.value) {
    console.log('[GraphEditor] 冻结状态下禁止绑定/解绑示波器');
    return;
  }
  
  if (oscId) {
    sessionStore.bindOutputNode(nodeId, oscId);
  } else {
    sessionStore.unbindOutputNode(nodeId);
  }
}

// 创建节点 HTML - 使用 X6 HTML 节点需要的特殊结构
function createNodeHtml(type: GraphNodeType, name: string) {
  const config = nodeTypes[type];
  return `
    <div class="x6-node" style="width: 100%; height: 100%;">
      <div style="
        width: 180px;
        height: 70px;
        background: white;
        border: 2px solid ${config.color};
        border-radius: 8px;
        display: flex;
        align-items: center;
        padding: 12px;
        gap: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        box-sizing: border-box;
      ">
        <div style="
          width: 36px;
          height: 36px;
          background: ${config.bg};
          color: ${config.color};
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 600;
          flex-shrink: 0;
        ">${config.icon}</div>
        <div style="flex: 1; min-width: 0; overflow: hidden;">
          <div style="font-size: 14px; font-weight: 500; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${name}</div>
          <div style="font-size: 11px; color: #999; margin-top: 2px;">${type}</div>
        </div>
      </div>
    </div>
  `;
}

function parseLegacyNumberList(raw: unknown): number[] {
  if (typeof raw !== 'string') return [];
  return raw
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((n) => !Number.isNaN(n));
}

function normalizeNodeParams(type: GraphNodeType, params: Record<string, unknown>) {
  const normalized = { ...params } as Record<string, unknown>;

  if (type === 'SOURCE') {
    normalized.sourceMode = String(normalized.sourceMode || 'live');
    normalized.sampleRate = Math.max(1, Number(normalized.sampleRate || 1000));
    normalized.channels = Math.max(1, Number(normalized.channels || 8));
    normalized.filePath = String(normalized.filePath || '');
    normalized.loop = Boolean(normalized.loop || false);
  }

  if (type === 'OSC') {
    normalized.saveEnabled = Boolean(normalized.saveEnabled || false);
    normalized.filename = String(normalized.filename || '');
    normalized.format = String(normalized.format || 'CSV');
  }

  if (type === 'SUM') {
    const existingInputs = Array.isArray(normalized.inputs) ? normalized.inputs as Array<Record<string, unknown>> : [];
    const legacyWeights = parseLegacyNumberList(normalized.weights);
    const inputs = existingInputs.length > 0
      ? existingInputs
      : (legacyWeights.length > 0
        ? legacyWeights.map((weight, idx) => ({ label: `输入${idx + 1}`, weight }))
        : [{ label: '输入1', weight: 1 }, { label: '输入2', weight: 1 }]);
    normalized.inputs = inputs.map((item, idx) => ({
      label: String(item.label || `输入${idx + 1}`),
      weight: Number(item.weight ?? 1),
    }));
    delete normalized.weights;
  }

  if (type === 'MERGE') {
    const existingInputs = Array.isArray(normalized.inputs) ? normalized.inputs as Array<Record<string, unknown>> : [];
    normalized.inputs = (existingInputs.length > 0 ? existingInputs : [{ label: '输入1', gain: 1 }, { label: '输入2', gain: 1 }])
      .map((item, idx) => ({
        label: String(item.label || `输入${idx + 1}`),
        gain: Number(item.gain ?? 1),
      }));
    normalized.strategy = String(normalized.strategy || 'interleave');
  }

  if (type === 'SPLIT') {
    const existingOutputs = Array.isArray(normalized.outputs) ? normalized.outputs as Array<Record<string, unknown>> : [];
    const legacyChannelIndices = typeof normalized.channelIndices === 'string' ? normalized.channelIndices : '0,1,2,3';
    normalized.outputs = (existingOutputs.length > 0 ? existingOutputs : [{ label: '输出1', channelIndices: legacyChannelIndices }])
      .map((item, idx) => ({
        label: String(item.label || `输出${idx + 1}`),
        channelIndices: String(item.channelIndices || ''),
      }));
    delete normalized.channelIndices;
  }

  if (type === 'CUSTOM_PYFUNC') {
    normalized.portMode = String(normalized.portMode || 'fixed');
    normalized.inputCount = Math.max(1, Number(normalized.inputCount || 2));
    normalized.outputCount = Math.max(1, Number(normalized.outputCount || 1));
    normalized.functionName = String(normalized.functionName || 'process_generated');
    normalized.windowMode = String(normalized.windowMode || 'seconds');
    normalized.windowSeconds = Math.max(0.01, Number(normalized.windowSeconds || 1));
    normalized.windowPoints = Math.max(1, Number(normalized.windowPoints || 256));
    normalized.hopMode = String(normalized.hopMode || 'points');
    normalized.hopPoints = Math.max(1, Number(normalized.hopPoints || 1));
    normalized.hopMs = Math.max(1, Number(normalized.hopMs || 10));
    normalized.outputSampleRate = Math.max(1, Number(normalized.outputSampleRate || 100));
    normalized.inputNames = Array.isArray(normalized.inputNames) ? normalized.inputNames : [];
    normalized.outputNames = Array.isArray(normalized.outputNames) ? normalized.outputNames : [];
    normalized.pythonEditableCode = String(normalized.pythonEditableCode || '');
    normalized.pythonCode = String(normalized.pythonCode || '');
  }

  if (type === 'DOWNSAMPLE' || type === 'UPSAMPLE') {
    normalized.mode = String(normalized.mode || 'targetRate');
    normalized.targetRate = Math.max(1, Number(normalized.targetRate || (type === 'DOWNSAMPLE' ? 250 : 1000)));
    normalized.factor = Math.max(1, Number(normalized.factor || 2));
  }

  if (type === 'CUSTOM_CONV') {
    const rawKernel = normalized.kernel;
    if (Array.isArray(rawKernel)) {
      normalized.kernel = rawKernel;
    } else if (typeof rawKernel === 'string') {
      normalized.kernel = rawKernel
        .split(',')
        .map((token) => Number(token.trim()))
        .filter((v) => Number.isFinite(v));
    } else {
      normalized.kernel = [0.25, 0.5, 0.25];
    }
  }

  return normalized;
}

function safePortCount(raw: unknown, fallback = 1): number {
  const parsed = Number(raw);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(1, Math.floor(parsed));
}

function getInputPortIds(type: GraphNodeType, params: Record<string, unknown>): string[] {
  if (type === 'SUM' || type === 'MERGE') {
    const inputs = Array.isArray(params.inputs) ? params.inputs : [];
    const count = Math.max(1, inputs.length || 1);
    return Array.from({ length: count }, (_, idx) => `in-${idx + 1}`);
  }
  const mode = String(params.portMode || 'fixed').toLowerCase();
  if (mode === 'adaptive') return nodeTypes[type].hasInput ? ['in'] : [];
  const count = safePortCount(params.inputCount, 1);
  if (count > 1 && nodeTypes[type].hasInput) {
    return Array.from({ length: count }, (_, idx) => `in-${idx + 1}`);
  }
  return nodeTypes[type].hasInput ? ['in'] : [];
}

function getOutputPortIds(type: GraphNodeType, params: Record<string, unknown>): string[] {
  if (type === 'SPLIT') {
    const outputs = Array.isArray(params.outputs) ? params.outputs : [];
    const count = Math.max(1, outputs.length || 1);
    return Array.from({ length: count }, (_, idx) => `out-${idx + 1}`);
  }
  const mode = String(params.portMode || 'fixed').toLowerCase();
  if (mode === 'adaptive') return nodeTypes[type].hasOutput ? ['out'] : [];
  const count = safePortCount(params.outputCount, 1);
  if (count > 1 && nodeTypes[type].hasOutput) {
    return Array.from({ length: count }, (_, idx) => `out-${idx + 1}`);
  }
  return nodeTypes[type].hasOutput ? ['out'] : [];
}

// 创建端口
function createPorts(type: GraphNodeType, params: Record<string, unknown>) {
  const config = nodeTypes[type];
  const inputPortIds = getInputPortIds(type, params);
  const outputPortIds = getOutputPortIds(type, params);
  const items = [
    ...inputPortIds.map((id) => ({ id, group: 'in' })),
    ...outputPortIds.map((id) => ({ id, group: 'out' })),
  ];
  return {
    groups: {
      in: {
        position: 'left',
        attrs: { circle: { r: 6, magnet: true, stroke: '#90A4AE', strokeWidth: 2, fill: '#fff', style: { visibility: 'hidden' } } },
      },
      out: {
        position: { name: 'right', args: { dx: -6 } },
        attrs: { circle: { r: 6, magnet: true, stroke: '#90A4AE', strokeWidth: 2, fill: '#fff', style: { visibility: 'hidden' } } },
      },
    },
    items,
  };
}

function syncNodePorts(node: import('@antv/x6').Node, type: GraphNodeType, params: Record<string, unknown>) {
  const graph = graphRef.value;
  if (!graph) return;

  const ports = createPorts(type, params);
  const dynamicNode = node as unknown as {
    setPorts?: (ports: unknown) => void;
    prop: (path: string, value: unknown) => void;
  };

  // 不同 X6 版本 API 有差异：优先调用 setPorts，不存在时回退到 prop('ports', ...)
  if (typeof dynamicNode.setPorts === 'function') {
    dynamicNode.setPorts(ports);
  } else {
    dynamicNode.prop('ports', ports);
  }

  const validInputPorts = new Set(getInputPortIds(type, params));
  const validOutputPorts = new Set(getOutputPortIds(type, params));

  graph.getConnectedEdges(node).forEach((edge) => {
    const sourceCellId = edge.getSourceCellId();
    const targetCellId = edge.getTargetCellId();
    const sourcePortId = edge.getSourcePortId();
    const targetPortId = edge.getTargetPortId();

    const invalidSourcePort = sourceCellId === node.id && sourcePortId && !validOutputPorts.has(sourcePortId);
    const invalidTargetPort = targetCellId === node.id && targetPortId && !validInputPorts.has(targetPortId);
    if (invalidSourcePort || invalidTargetPort) {
      edge.remove();
    }
  });
}

function getDefaultNodeInputPort(nodeId: string): string {
  const graph = graphRef.value;
  if (!graph) return 'in';
  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return 'in';
  const data = node.getData() as GraphNode;
  const params = (data?.params || {}) as Record<string, unknown>;
  return getInputPortIds(data.type, params)[0] || 'in';
}

function getDefaultNodeOutputPort(nodeId: string): string {
  const graph = graphRef.value;
  if (!graph) return 'out';
  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return 'out';
  const data = node.getData() as GraphNode;
  const params = (data?.params || {}) as Record<string, unknown>;
  return getOutputPortIds(data.type, params)[0] || 'out';
}

function formatEdgeChannelLabel(channelNames: string[], sampleRate?: number | null) {
  const rateText = Number.isFinite(sampleRate) && (sampleRate || 0) > 0
    ? `\n${Math.round(sampleRate || 0)} sps`
    : '';
  if (channelNames.length === 0) return '无通道';
  return `${channelNames.length}ch${rateText}`;
}

function getEdgeTooltipText(channelNames: string[]): string {
  if (channelNames.length === 0) return '无通道';
  if (channelNames.length <= 8) return channelNames.join('\n');
  return `${channelNames.slice(0, 8).join('\n')}\n... (共${channelNames.length}个通道)`;
}

function parsePortIndex(portId: string | undefined, fallback = 0) {
  if (!portId) return fallback;
  const match = portId.match(/-(\d+)$/);
  if (!match) return fallback;
  const parsed = Number(match[1]);
  return Number.isFinite(parsed) ? Math.max(0, parsed - 1) : fallback;
}

function parseIndices(raw: unknown): number[] {
  if (Array.isArray(raw)) {
    return raw
      .map((item) => Number(item))
      .filter((n) => Number.isInteger(n) && n >= 0);
  }
  if (typeof raw !== 'string') return [];
  return raw
    .replace(/，/g, ',')
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((n) => Number.isInteger(n) && n >= 0);
}

function defaultChannelNames(count: number) {
  return Array.from({ length: Math.max(0, count) }, (_, idx) => `CH${idx + 1}`);
}

function inferNodeOutputChannels(nodeId: string, sourcePort?: string, visited = new Set<string>()): string[] {
  const graph = graphRef.value;
  if (!graph) return [];
  if (visited.has(nodeId)) return [];
  visited.add(nodeId);

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return [];
  const data = node.getData() as GraphNode;
  const params = (data.params || {}) as Record<string, unknown>;

  const incomingEdges = (graph.getIncomingEdges(node) || [])
    .slice()
    .sort((a, b) => (a.getTargetPortId() || '').localeCompare(b.getTargetPortId() || ''));

  if (data.type === 'SOURCE') {
    const names = Array.isArray(params.channelNames) ? params.channelNames.map((n) => String(n)) : [];
    if (names.length > 0) return names;
    const channels = Number(params.channels || 8);
    return defaultChannelNames(Number.isFinite(channels) ? channels : 8);
  }

  if (data.type === 'REPLAY') {
    const names = Array.isArray(params.channelNames) ? params.channelNames.map((n) => String(n)) : [];
    return names.length > 0 ? names : defaultChannelNames(8);
  }

  const upstreamEdge = incomingEdges[0];
  const upstreamNodeId = upstreamEdge?.getSourceCellId();
  const upstreamPortId = upstreamEdge?.getSourcePortId() || undefined;
  const upstreamChannels = upstreamNodeId ? inferNodeOutputChannels(upstreamNodeId, upstreamPortId, visited) : [];

  if (data.type === 'FILTER') {
    return upstreamChannels;
  }

  if (data.type === 'SUM') {
    return [data.name || 'SUM'];
  }

  if (data.type === 'MERGE') {
    const merged: string[] = [];
    incomingEdges.forEach((edge) => {
      const sourceId = edge.getSourceCellId();
      if (!sourceId) return;
      const sourceNames = inferNodeOutputChannels(sourceId, edge.getSourcePortId() || undefined, new Set(visited));
      merged.push(...sourceNames);
    });
    return merged;
  }

  if (data.type === 'SPLIT') {
    const paramsOutputs = Array.isArray(params.outputs) ? params.outputs as Array<Record<string, unknown>> : [];
    const outputIdx = parsePortIndex(sourcePort, 0);
    const outputCfg = paramsOutputs[outputIdx] || paramsOutputs[0];
    const indices = parseIndices(outputCfg?.channelIndices);
    const selected = indices.map((idx) => upstreamChannels[idx]).filter((name): name is string => Boolean(name));
    if (selected.length > 0) return selected;
    if (typeof outputCfg?.label === 'string' && outputCfg.label.trim() !== '') {
      return [outputCfg.label.trim()];
    }
    return upstreamChannels;
  }

  return upstreamChannels;
}

function inferNodeOutputSampleRate(nodeId: string, sourcePort?: string, visited = new Set<string>()): number | null {
  const graph = graphRef.value;
  if (!graph) return null;
  if (visited.has(nodeId)) return null;
  visited.add(nodeId);

  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return null;
  const data = node.getData() as GraphNode;
  const params = (data.params || {}) as Record<string, unknown>;

  const incomingEdges = (graph.getIncomingEdges(node) || [])
    .slice()
    .sort((a, b) => (a.getTargetPortId() || '').localeCompare(b.getTargetPortId() || ''));

  if (data.type === 'SOURCE' || data.type === 'REPLAY') {
    const sr = Number(params.sampleRate || 1000);
    return Number.isFinite(sr) && sr > 0 ? sr : 1000;
  }

  const upstreamEdge = incomingEdges[0];
  const upstreamNodeId = upstreamEdge?.getSourceCellId();
  const upstreamPortId = upstreamEdge?.getSourcePortId() || undefined;
  const upstreamRate = upstreamNodeId ? inferNodeOutputSampleRate(upstreamNodeId, upstreamPortId, visited) : null;

  if (data.type === 'DOWNSAMPLE') {
    const inRate = upstreamRate || 1000;
    const mode = String(params.mode || 'targetRate').toLowerCase();
    if (mode === 'factor') {
      const factor = Math.max(1, Number(params.factor || 2));
      return inRate / factor;
    }
    const targetRate = Math.max(1, Number(params.targetRate || inRate / 2));
    return Math.min(inRate, targetRate);
  }

  if (data.type === 'UPSAMPLE') {
    const inRate = upstreamRate || 1000;
    const mode = String(params.mode || 'targetRate').toLowerCase();
    if (mode === 'factor') {
      const factor = Math.max(1, Number(params.factor || 2));
      return inRate * factor;
    }
    return Math.max(1, Number(params.targetRate || inRate));
  }

  if (data.type === 'CUSTOM_PYFUNC') {
    const inRate = upstreamRate || 1000;
    const hopMode = String(params.hopMode || 'points').toLowerCase();
    if (hopMode === 'targetRate') {
      return Math.max(1, Number(params.outputSampleRate || inRate));
    }
    if (hopMode === 'milliseconds') {
      const hopMs = Math.max(1, Number(params.hopMs || 10));
      return 1000 / hopMs;
    }
    const hopPoints = Math.max(1, Number(params.hopPoints || 1));
    return inRate / hopPoints;
  }

  return upstreamRate;
}

function inferEdgeChannelNames(edge: import('@antv/x6').Edge): string[] {
  const graph = graphRef.value;
  if (!graph) return [];

  const sourceNodeId = edge.getSourceCellId();
  if (!sourceNodeId) return [];
  const sourceNode = graph.getCellById(sourceNodeId);
  if (!sourceNode || !sourceNode.isNode()) return [];

  const sourceData = sourceNode.getData() as GraphNode;
  const sourcePort = edge.getSourcePortId() || 'out';

  if (sourceData.type === 'SPLIT') {
    const params = (sourceData.params || {}) as Record<string, unknown>;
    const outputs = Array.isArray(params.outputs) ? params.outputs as Array<Record<string, unknown>> : [];
    const outputIdx = parsePortIndex(sourcePort, 0);
    const outputCfg = outputs[outputIdx] || outputs[0];

    const incomingEdges = graph.getIncomingEdges(sourceNode) || [];
    const inputEdge = incomingEdges[0];
    const upstreamId = inputEdge?.getSourceCellId();
    const upstreamNames = upstreamId ? inferNodeOutputChannels(upstreamId) : [];
    const indices = parseIndices(outputCfg?.channelIndices);
    const selected = indices.map((idx) => upstreamNames[idx]).filter((name): name is string => Boolean(name));
    if (selected.length > 0) return selected;
    if (typeof outputCfg?.label === 'string' && outputCfg.label.trim() !== '') {
      return [outputCfg.label.trim()];
    }
    return [];
  }

  if (sourceData.type === 'SUM') {
    return [sourceData.name || 'SUM'];
  }

  return inferNodeOutputChannels(sourceNodeId, sourcePort);
}

function applyEdgeLabel(edge: import('@antv/x6').Edge) {
  const channelNames = inferEdgeChannelNames(edge);
  const sourceNodeId = edge.getSourceCellId();
  const sourcePort = edge.getSourcePortId() || undefined;
  const sampleRate = sourceNodeId ? inferNodeOutputSampleRate(sourceNodeId, sourcePort) : null;
  const label = formatEdgeChannelLabel(channelNames, sampleRate);
  const tooltipText = getEdgeTooltipText(channelNames);
  
  edge.setLabels([
    {
      position: {
        distance: 0.5,
        options: {
          keepGradient: true,
          ensureLegibility: true,
        },
      },
      attrs: {
        label: {
          text: label,
          fill: '#546E7A',
          fontSize: 11,
          textAnchor: 'middle',
          textVerticalAnchor: 'middle',
          cursor: 'help',
        },
        rect: {
          fill: '#ffffff',
          stroke: '#CFD8DC',
          strokeWidth: 1,
          rx: 8,
          ry: 8,
          refWidth: '120%',
          refHeight: '140%',
          refX: '-10%',
          refY: '-20%',
          cursor: 'help',
        },
      },
    },
  ]);
  
  // 添加tooltip
  edge.setAttrByPath('label/title', tooltipText);
  edge.setAttrByPath('labelContainer/title', tooltipText);
}

function updateAllEdgeLabels() {
  const graph = graphRef.value;
  if (!graph) return;
  graph.getEdges().forEach((edge) => applyEdgeLabel(edge));
}

// 添加节点 - 使用 rect 形状配合 attrs
function addNode(type: GraphNodeType, x: number, y: number, name?: string, params?: Record<string, unknown>, existingId?: string) {
  const graph = graphRef.value;
  if (!graph) return null;

  const config = nodeTypes[type];
  // 优先使用传入的ID（从后端加载时），确保ID有效
  const nodeId = existingId && existingId.trim() !== '' 
    ? existingId 
    : `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;

  // 初始化默认参数
  const paramConfig = nodeParamConfigs[type];
  const defaultParams: Record<string, unknown> = {};
  paramConfig.forEach((field) => {
    defaultParams[field.key] = field.default;
  });

  // 合并传入的参数
  const nodeParams = normalizeNodeParams(type, { ...defaultParams, ...params });

  // 生成带属性的标签文本
  const labelText = generateNodeLabel(type, name || config.name, nodeParams, nodeId);

  const node = graph.addNode({
    id: nodeId,
    shape: 'rect',
    x,
    y,
    width: 180,
    height: 70,
    attrs: {
      body: {
        fill: '#fff',
        stroke: config.color,
        strokeWidth: 2,
        rx: 8,
        ry: 8,
      },
      label: {
        text: labelText,
        fill: '#333',
        fontSize: 12,
        fontWeight: 500,
        refY: 0.5,
        textVerticalAnchor: 'middle',
      },
    },
    ports: createPorts(type, nodeParams),
    data: { type, name: name || config.name, params: nodeParams },
  });

  hasNodes.value = true;
  return node;
}

// 生成节点标签（显示名称+关键属性+绑定状态）
function generateNodeLabel(type: GraphNodeType, name: string, params: Record<string, unknown>, nodeId?: string): string {
  const keyParam = getKeyParamDisplay(type, params);
  // 检查节点是否被示波器视图绑定
  const isBound = nodeId ? sessionStore.isNodeBoundByView(nodeId) : false;
  console.log('[generateNodeLabel] nodeId:', nodeId, 'isBound:', isBound);
  const boundIndicator = isBound ? '🔗 ' : '';
  
  if (keyParam) {
    return `${boundIndicator}${name}\n${keyParam}`;
  }
  return `${boundIndicator}${name}`;
}

// 获取节点关键属性显示文本
function getKeyParamDisplay(type: GraphNodeType, params: Record<string, unknown>): string {
  switch (type) {
    case 'FILTER':
      const filterType = params['type'] || 'lowpass';
      const cutoff = params['cutoff'] || 50;
      return `${filterType} ${cutoff}Hz`;
    case 'DOWNSAMPLE': {
      const mode = String(params['mode'] || 'targetRate');
      if (mode === 'factor') return `/${Math.max(1, Number(params['factor'] || 2))}`;
      return `→${Math.max(1, Number(params['targetRate'] || 250))}Hz`;
    }
    case 'UPSAMPLE': {
      const mode = String(params['mode'] || 'targetRate');
      if (mode === 'factor') return `x${Math.max(1, Number(params['factor'] || 2))}`;
      return `→${Math.max(1, Number(params['targetRate'] || 1000))}Hz`;
    }
    case 'OSC':
      const timeWindow = params['timeWindow'] || 5;
      const mode = params['mode'] || 'scroll';
      return `${timeWindow}s ${mode}`;
    case 'SOURCE':
      const sampleRate = params['sampleRate'] || 1000;
      const channels = params['channels'] || 8;
      return `${sampleRate}Hz ${channels}ch`;
    case 'SPECTRUM':
      const fftSize = params['fftSize'] || '1024';
      return `FFT ${fftSize}`;
    case 'SAVE':
      const format = params['format'] || 'edf';
      return `.${format}`;
    case 'SUM': {
      const inputs = Array.isArray(params['inputs']) ? params['inputs'] : [];
      return `${inputs.length || 0}路输入`;
    }
    case 'SPLIT': {
      const outputs = Array.isArray(params['outputs']) ? params['outputs'] : [];
      return `${outputs.length || 0}路输出`;
    }
    case 'MERGE': {
      const inputs = Array.isArray(params['inputs']) ? params['inputs'] : [];
      const strategy = params['strategy'] || 'interleave';
      return `${inputs.length || 0}→1 ${strategy}`;
    }
    case 'CUSTOM_PYFUNC': {
      const mode = params['portMode'] || 'fixed';
      const inputCount = Number(params['inputCount'] || 2);
      const outputCount = Number(params['outputCount'] || 1);
      const hopMode = String(params['hopMode'] || 'points');
      const hopDesc = hopMode === 'targetRate'
        ? `${Math.max(1, Number(params['outputSampleRate'] || 100))}Hz`
        : (hopMode === 'milliseconds' ? `${Math.max(1, Number(params['hopMs'] || 10))}ms` : `${Math.max(1, Number(params['hopPoints'] || 1))}pt`);
      if (String(mode) === 'adaptive') return 'I/O 自适应';
      return `${inputCount}→${outputCount} @${hopDesc}`;
    }
    case 'CUSTOM_CONV': {
      const kernel = Array.isArray(params['kernel']) ? params['kernel'] : [];
      return `kernel=${kernel.length || 0}`;
    }
    default:
      return '';
  }
}

// 拖拽开始
function onDragStart(e: DragEvent, type: GraphNodeType) {
  // 检查编辑权限
  if (!canEditGraphLocal.value) {
    e.preventDefault();
    alert(`当前状态不允许添加节点: ${statusDescription.value}`);
    return;
  }
  
  e.dataTransfer?.setData('node-type', type);
  e.dataTransfer!.effectAllowed = 'copy';
}

// 从后端加载数据
async function loadFromBackend() {
  try {
    console.log('[GraphEditor] Loading graph from backend...');
    const backendPayload = await fetchGraph();

    // 立即获取运行时状态
    try {
      await pollRuntimeState();
    } catch (e) {
      console.warn('[GraphEditor] Failed to poll runtime state on load:', e);
    }

    applyPayloadToCanvas(backendPayload, { fromBackend: true });
  } catch (err) {
    console.error('Failed to load graph:', err);
    hasNodes.value = false;
  }
}

function applyPayloadToCanvas(payload: GraphPayload, options?: { fromBackend?: boolean }) {
  const graph = graphRef.value;
  if (!graph) return;

  isApplyingBackendGraph.value = true;
  try {
    const safePayload: GraphPayload = {
      nodes: Array.isArray(payload.nodes) ? payload.nodes : [],
      edges: Array.isArray(payload.edges) ? payload.edges : [],
      frozen: Boolean(payload.frozen),
    };

    setRuntimeState({ frozen: safePayload.frozen });
    graph.clearCells();

    safePayload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    safePayload.edges.forEach((edge) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (!sourceNode || !targetNode) return;
      graph.addEdge({
        id: edge.id,
        source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
        target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
        attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
      });
    });

    hasNodes.value = graph.getNodes().length > 0;
    updateAllEdgeLabels();
    setGraphInteracting(graph, !frozen.value);

    if (options?.fromBackend) {
      lastSyncedSignature.value = payloadSignature(safePayload);
      hasUnsavedChanges.value = false;
    }
  } finally {
    isApplyingBackendGraph.value = false;
  }
}

function setGraphInteracting(graph: Graph, enabled: boolean) {
  // X6 2.x: 使用 options 配置交互状态
  if (graph) {
    // 考虑编辑权限
    const actuallyEnabled = enabled && canEditGraphLocal.value;
    graph.options.interacting = actuallyEnabled ? {
      nodeMovable: true,
      edgeMovable: true,
      edgeLabelMovable: true,
      arrowheadMovable: true,
      vertexMovable: true,
      vertexAddable: true,
      vertexDeletable: true,
    } : false;
    
    // 更新界面提示
    if (!actuallyEnabled && enabled) {
      console.log('[GraphEditor] Graph editing disabled due to permissions');
    }
  }
}

async function applyFrozen() {
  const graph = graphRef.value;
  if (!graph) {
    console.warn('[GraphEditor] applyFrozen: graph ref is null');
    return;
  }

  console.log(`[GraphEditor] applyFrozen called, frozen: ${frozen.value}, isRunning: ${isRunning.value}`);

  // 更新图形编辑权限
  if (graph) {
    setGraphInteracting(graph, !frozen.value);
  }
  
  if (frozen.value) {
    console.log('[GraphEditor] Graph is frozen, disabling editing');
    
    // 如果计算图正在运行，自动建立WebSocket连接
    if (isRunning.value) {
      console.log('[GraphEditor] Graph is running, connecting WebSocket...');
      await connectWebSocket();
      console.log('[GraphEditor] WebSocket connected for running graph');
    }
  } else {
    console.log('[GraphEditor] Graph is unfrozen, enabling editing');
    
    // 如果计算图未运行，断开WebSocket连接
    if (!isRunning.value) {
      console.log('[GraphEditor] Graph is not running, disconnecting WebSocket...');
      disconnectWebSocket();
      console.log('[GraphEditor] WebSocket disconnected');
    }
  }
}

function buildPayload(): GraphPayload {
  const graph = graphRef.value;
  if (!graph) return { nodes: [], edges: [], frozen: frozen.value };

  const nodes: GraphNode[] = graph.getNodes().map((node) => {
    const data = node.getData() as GraphNode;
    const { x, y } = node.position();
    return { ...data, id: node.id, x, y };
  });

  const edges = graph.getEdges().map((edge) => ({
    id: edge.id,
    source: edge.getSourceCellId() || '',
    target: edge.getTargetCellId() || '',
    sourcePort: edge.getSourcePortId() || undefined,
    targetPort: edge.getTargetPortId() || undefined,
  }));

  return { nodes, edges, frozen: frozen.value };
}

// 保存状态到会话存储
function saveStateToSessionStorage() {
  try {
    const graph = graphRef.value;
    if (!graph) return;

    const payload = buildPayload();
    
    // 只保存有效的状态（有节点或计算图正在运行）
    const isValidState = payload.nodes.length > 0 || isRunning.value;
    if (!isValidState) {
      console.log('[GraphEditor] Skipping session storage save - empty graph and not running');
      return;
    }
    
    const state = {
      payload,
      isRunning: isRunning.value,
      runtimeMode: runtimeMode.value,
      timestamp: Date.now()
    };
    
    sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state));
    console.log('[GraphEditor] State saved to session storage:', {
      nodes: payload.nodes.length,
      edges: payload.edges.length,
      frozen: payload.frozen,
      isRunning: isRunning.value
    });
  } catch (err) {
    console.error('[GraphEditor] Failed to save state to session storage:', err);
  }
}

// 从会话存储恢复状态到画布
function restoreStateFromSessionStorage(): boolean {
  try {
    const graph = graphRef.value;
    if (!graph) return false;

    const stateJson = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!stateJson) return false;

    const state = JSON.parse(stateJson);
    if (!state.payload || !state.payload.nodes || state.payload.nodes.length === 0) {
      return false;
    }

    console.log('[GraphEditor] Restoring state from session storage to canvas:', {
      nodes: state.payload.nodes.length,
      edges: state.payload.edges.length,
      frozen: state.payload.frozen,
      isRunning: state.isRunning
    });

    // 清空画布
    graph.clearCells();

    // 恢复节点
    state.payload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        console.warn('Node without id:', node);
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    // 恢复边
    state.payload.edges.forEach((edge: any) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (sourceNode && targetNode) {
        graph.addEdge({
          id: edge.id,
          source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
          target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    // 恢复状态
    setRuntimeState({ frozen: state.payload.frozen });
    if (state.isRunning) {
      setRuntimeState({
        isRunning: state.isRunning,
        runtimeMode: state.runtimeMode,
      });
    }

    const finalNodeCount = graph.getNodes().length;
    const finalEdgeCount = graph.getEdges().length;
    hasNodes.value = finalNodeCount > 0;
    
    updateAllEdgeLabels();
    setGraphInteracting(graph, !frozen.value);
    
    console.log(`[GraphEditor] State restored - Canvas has ${finalNodeCount} nodes, ${finalEdgeCount} edges`);
    return true;
  } catch (err) {
    console.error('[GraphEditor] Failed to restore state from session storage:', err);
    return false;
  }
}

// 从会话存储加载状态
function loadStateFromSessionStorage(): boolean {
  try {
    const stateJson = sessionStorage.getItem(SESSION_STORAGE_KEY);
    if (!stateJson) return false;

    const state = JSON.parse(stateJson);
    console.log('[GraphEditor] Loaded state from session storage:', state);
    
    // 检查状态是否过期（超过5分钟）
    const isExpired = Date.now() - state.timestamp > 5 * 60 * 1000;
    if (isExpired) {
      console.log('[GraphEditor] Session storage state expired, clearing');
      sessionStorage.removeItem(SESSION_STORAGE_KEY);
      return false;
    }
    
    return true;
  } catch (err) {
    console.error('[GraphEditor] Failed to load state from session storage:', err);
    return false;
  }
}

// 清除会话存储状态
function clearSessionStorage() {
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
  console.log('[GraphEditor] Cleared session storage');
}

async function save() {
  console.log('[GraphEditor] Save button clicked, frozen:', frozen.value);

  if (!hasUnsavedChanges.value) {
    return;
  }
  
  // 检查计算图是否正在运行
  if (isRunning.value) {
    console.log('[GraphEditor] Graph is running, skipping save');
    alert('计算图正在运行中，无法保存。请先停止运行再保存。');
    return;
  }
  
  try {
    const payload = buildPayload();
    console.log('[GraphEditor] Saving graph with payload:', payload);
    await saveGraph(payload);
    console.log('[GraphEditor] Graph saved successfully');

    lastSyncedSignature.value = payloadSignature(payload);
    hasUnsavedChanges.value = false;
    
    // 保存状态到会话存储
    saveStateToSessionStorage();
  } catch (err) {
    console.error('[GraphEditor] Failed to save graph:', err);
    alert('保存失败: ' + (err as Error).message);
  }
}

// 导出计算图为 JSON 文件
function exportGraph() {
  const payload = buildPayload();
  const json = JSON.stringify(payload, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `eeg-graph-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
  console.log('[GraphEditor] Graph exported');
}

// 触发文件选择
function triggerFileLoad() {
  const input = document.getElementById('graph-file-input') as HTMLInputElement;
  if (input) {
    input.click();
  }
}

// 从文件加载计算图
async function loadGraphFromFile(event: Event) {
  // 检查编辑权限
  if (!canEditGraph.value) {
    alert(`当前状态不允许加载计算图: ${statusDescription.value}`);
    // 清空input以便可以再次选择同一文件
    const input = event.target as HTMLInputElement;
    input.value = '';
    return;
  }
  
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  try {
    const text = await file.text();
    const payload = JSON.parse(text) as GraphPayload;
    
    // 验证数据结构
    if (!payload.nodes || !Array.isArray(payload.nodes) || !payload.edges || !Array.isArray(payload.edges)) {
      alert('无效的计算图文件格式');
      return;
    }

    const graph = graphRef.value;
    if (!graph) return;

    // 清空当前画布
    graph.clearCells();

    // 加载节点
    payload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        console.warn('Node without id:', node);
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    // 加载边
    payload.edges.forEach((edge) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (sourceNode && targetNode) {
        graph.addEdge({
          id: edge.id,
          source: { cell: edge.source, port: edge.sourcePort || getDefaultNodeOutputPort(edge.source) },
          target: { cell: edge.target, port: edge.targetPort || getDefaultNodeInputPort(edge.target) },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    hasNodes.value = graph.getNodes().length > 0;
    setRuntimeState({ frozen: payload.frozen || false });
    updateAllEdgeLabels();
    syncUnsavedState();
    
    console.log('[GraphEditor] Graph loaded from file:', file.name);
    alert('计算图加载成功，请点击保存应用到后端。');
  } catch (err) {
    console.error('[GraphEditor] Failed to load graph from file:', err);
    alert('加载失败: ' + (err as Error).message);
  } finally {
    // 清空 input 以便可以再次选择同一文件
    input.value = '';
  }
}

async function run(mode: 'live' | 'offline' = 'live') {
  console.log('[GraphEditor] Run button clicked, mode:', mode, 'frozen:', frozen.value, 'hasNodes:', hasNodes.value);
  
  // 检查计算图是否已经在运行
  if (isRunning.value) {
    console.log('[GraphEditor] Graph is already running');
    return;
  }
  
  // 启动 runtime（会验证冻结状态并连接 WebSocket）
  const success = await graphRuntime.start();
  if (!success) {
    console.error('[GraphEditor] Failed to start runtime:', graphRuntime.state.error);
    alert(`启动失败: ${graphRuntime.state.error}`);
    return;
  }
  
  console.log('[GraphEditor] Runtime started, calling runGraph API');
  // 调用后端API
  try {
    await graphRuntimeStore.runByMode(mode);
    console.log('[GraphEditor] Graph run API called successfully');
    {
      setRuntimeState({
        isRunning: true,
        runtimeMode: mode,
        offlineProgress: 0,
      });
      startRuntimeStatePolling();
      
      // 启动边动画（live和offline模式都有动画，但效果不同）
      startEdgeAnimations();
      
      // 调试：记录当前画布状态
      const graph = graphRef.value;
      if (graph) {
        const nodeCount = graph.getNodes().length;
        const edgeCount = graph.getEdges().length;
        console.log(`[GraphEditor] After run - Canvas has ${nodeCount} nodes, ${edgeCount} edges`);
      }
      
      // 保存状态到会话存储
      saveStateToSessionStorage();
    }
  } catch (err) {
    console.error('[GraphEditor] Failed to run graph:', err);
    alert('运行失败: ' + (err as Error).message);
    return;
  }
  
  // 监听WebSocket连接状态变化
  const checkWebSocketConnection = () => {
    if (eegWebSocket.isConnected()) {
      console.log('[GraphEditor] WebSocket connected successfully');
      console.log('WebSocket连接成功，使用真实后端数据');
    } else {
      console.log('[GraphEditor] WebSocket not connected yet, waiting for connection...');
      console.log('WebSocket尚未连接，等待连接...');
      // 设置一个超时检查，如果5秒后仍未连接，提示用户
      setTimeout(() => {
        if (!eegWebSocket.isConnected()) {
          console.warn('[GraphEditor] WebSocket still not connected after 5 seconds');
          console.warn('WebSocket连接超时，请检查后端服务是否运行');
        }
      }, 5000);
    }
  };
  
  // 立即检查一次
  checkWebSocketConnection();
  
  // 监听WebSocket状态变化
  const unsubscribe = eegWebSocket.onStatusChange((status) => {
    console.log('[GraphEditor] WebSocket status changed:', status);
    if (status === 'connected') {
      console.log('[GraphEditor] WebSocket connected, using real backend data');
      console.log('WebSocket已连接，使用真实后端数据');
    } else if (status === 'error') {
      console.error('[GraphEditor] WebSocket connection error');
      console.error('WebSocket连接错误，请检查后端服务');
    }
  });
  
  // 在组件卸载时取消监听
  onUnmounted(() => {
    unsubscribe();
  });
}

// 模拟数据流（用于测试）
let dataInterval: number | null = null;

// 方波生成函数
function squareWave(t: number, freq: number): number {
  return Math.sign(Math.sin(2 * Math.PI * freq * t));
}

function startMockDataStream() {
  if (dataInterval) clearInterval(dataInterval);

  const startTime = Date.now() / 1000;
  dataInterval = window.setInterval(() => {
    if (!graphRuntime.state.isRunning) {
      if (dataInterval) clearInterval(dataInterval);
      return;
    }

    const t = Date.now() / 1000;
    const elapsed = t - startTime;

    // 生成方波测试数据 - 用于验证计算图处理流程
    const channels = Array.from({ length: 8 }, (_, i) => {
      // 基础方波 (5-10 Hz) - 易于观察处理效果
      const freq = 5 + i * 0.5;
      const squareSignal = squareWave(elapsed, freq) * 30;

      // 高频干扰 (50-150 Hz)
      const highFreq1 = 50 + i * 10;
      const highFreq2 = 120 + i * 5;
      const highFreqNoise = Math.sin(2 * Math.PI * highFreq1 * elapsed) * 20 +
                            Math.sin(2 * Math.PI * highFreq2 * elapsed) * 15;

      // 随机噪声
      const randomNoise = (Math.random() - 0.5) * 10;

      // 组合信号：方波 + 高频噪声 + 随机噪声
      return squareSignal + highFreqNoise + randomNoise;
    });

    graphRuntime.emitPacket({ t, channels });
  }, 10); // 100Hz 采样率，才能显示高频信号
}

function stopMockDataStream() {
  if (dataInterval) {
    clearInterval(dataInterval);
    dataInterval = null;
  }
}

function clear() {
  // 检查编辑权限
  if (!canEditGraph.value) {
    alert(`当前状态不允许清空计算图: ${statusDescription.value}`);
    return;
  }
  
  if (!confirm('确定要清空计算图吗？所有节点和边将被删除。')) return;
  
  const graph = graphRef.value;
  if (!graph) return;
  
  // 停止运行时
  graphRuntime.stop();
  stopMockDataStream();
  stopRuntimeStatePolling();
  stopEdgeAnimations();
  setRuntimeState({
    isRunning: false,
    offlineProgress: 0,
    processingDelayMs: 0,
    nonRealtime: false,
    runtimeWarning: null,
  });
  
  graph.clearCells();
  hasNodes.value = false;
  
  // 清除会话存储
  clearSessionStorage();
}

async function loadMockData() {
  // 检查编辑权限
  if (!canEditGraph.value) {
    alert(`当前状态不允许加载Mock数据: ${statusDescription.value}`);
    return;
  }
  
  const graph = graphRef.value;
  if (!graph) return;

  graph.clearCells();

  const nodes = [
    { type: 'SOURCE' as GraphNodeType, x: 50, y: 100, name: '脑电数据源' },
    { type: 'FILTER' as GraphNodeType, x: 300, y: 100, name: '低通滤波器' },
    { type: 'SPLIT' as GraphNodeType, x: 550, y: 100, name: '通道分离' },
    { type: 'OSC' as GraphNodeType, x: 800, y: 100, name: '波形显示器' },
  ];

  const nodeIds: string[] = [];
  nodes.forEach((n) => {
    const node = addNode(n.type, n.x, n.y, n.name);
    if (node) nodeIds.push(node.id);
  });

  // 创建边
  if (nodeIds.length >= 4) {
    graph.addEdge({
      source: { cell: nodeIds[0], port: 'out' },
      target: { cell: nodeIds[1], port: 'in' },
      attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
    });
    graph.addEdge({
      source: { cell: nodeIds[1], port: 'out' },
      target: { cell: nodeIds[2], port: 'in' },
      attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
    });
    graph.addEdge({
      source: { cell: nodeIds[2], port: 'out-1' },
      target: { cell: nodeIds[3], port: 'in' },
      attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
    });
  }

  updateAllEdgeLabels();
  syncUnsavedState();
  
  // 保存状态到会话存储
  saveStateToSessionStorage();
}

onMounted(async () => {
  if (!container.value) return;

  window.addEventListener('keydown', onSaveHotkey);
  window.addEventListener('beforeunload', onBeforeUnload);

  // 创建画布
  const graph = new Graph({
    container: container.value,
    grid: { size: 10, visible: true, type: 'dot' },
    background: { color: '#fafafa' },
    panning: { enabled: true, eventTypes: ['leftMouseDown'] },
    mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'] },
    connecting: {
      snap: { radius: 20 },
      allowBlank: false,
      allowLoop: false,
      allowEdge: false,
      highlight: true,
      router: {
        name: 'metro',
        args: {
          startDirections: ['top', 'right', 'bottom', 'left'],
          endDirections: ['top', 'right', 'bottom', 'left'],
          padding: 10,
          step: 10,
        },
      },
      createEdge() {
        return graph.createEdge({
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      },
      validateConnection({ sourceMagnet, targetMagnet }) {
        if (!sourceMagnet || sourceMagnet.getAttribute('port-group') === 'in') return false;
        if (!targetMagnet || targetMagnet.getAttribute('port-group') !== 'in') return false;

        const targetPort = targetMagnet.getAttribute('port');
        const targetCellId = targetMagnet.getAttribute('data-cell-id');
        if (targetCellId && targetPort) {
          const hasIncoming = graph.getEdges().some((edge) => {
            return edge.getTargetCellId() === targetCellId && edge.getTargetPortId() === targetPort;
          });
          if (hasIncoming) return false;
        }
        return true;
      },
    },
    highlighting: {
      magnetAdsorbed: {
        name: 'stroke',
        args: { attrs: { fill: '#5F95FF', stroke: '#5F95FF' } },
      },
    },
  });

  graphRef.value = graph;

  unsubscribeGraphSync = graphSyncWebSocket.onGraph(({ graph: backendGraph, reason }) => {
    const incomingSignature = payloadSignature(backendGraph);
    if (incomingSignature === lastSyncedSignature.value && !hasUnsavedChanges.value) {
      return;
    }
    if (hasUnsavedChanges.value) {
      console.warn('[GraphEditor] Local unsaved changes were replaced by backend graph sync update:', reason);
    }
    applyPayloadToCanvas(backendGraph, { fromBackend: true });
  });
  graphSyncWebSocket.connect();

  // 添加对齐线
  graph.use(new Snapline({ enabled: true }));

  // 拖拽放置处理
  container.value.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'copy';
  });

  container.value.addEventListener('drop', (e) => {
    e.preventDefault();
    const type = e.dataTransfer?.getData('node-type') as GraphNodeType;
    if (!type || !container.value) return;

    const rect = container.value.getBoundingClientRect();
    const x = e.clientX - rect.left - 90;
    const y = e.clientY - rect.top - 35;

    addNode(type, x, y);
  });

  // 节点悬停显示端口
  graph.on('node:mouseenter', ({ node }) => {
    node.getPorts().forEach((port) => {
      node.setPortProp(port.id!, 'attrs/circle/style/visibility', 'visible');
    });
  });

  graph.on('node:mouseleave', ({ node }) => {
    node.getPorts().forEach((port) => {
      const edges = graph.getConnectedEdges(node);
      const isConnected = edges.some((e) =>
        e.getSourcePortId() === port.id || e.getTargetPortId() === port.id
      );
      node.setPortProp(port.id!, 'attrs/circle/style/visibility', isConnected ? 'visible' : 'hidden');
      node.setPortProp(port.id!, 'attrs/circle/fill', isConnected ? '#5F95FF' : '#fff');
    });
  });

  // 边悬停显示删除按钮
  graph.on('edge:mouseenter', ({ edge }) => {
    edge.addTools({ name: 'button-remove', args: { distance: -40 } });
  });

  graph.on('edge:mouseleave', ({ edge }) => {
    edge.removeTools();
  });

  // 节点悬停显示删除按钮
  graph.on('node:mouseenter', ({ node }) => {
    node.addTools({
      name: 'button-remove',
      args: {
        x: '100%',
        y: 0,
        offset: { x: -10, y: 10 },
        onClick({ cell }: { cell: any }) {
          graph.removeCell(cell);
        }
      }
    });
  });

  graph.on('node:mouseleave', ({ node }) => {
    node.removeTools();
  });

  // 连接成功高亮
  graph.on('edge:connected', ({ edge, currentCell, currentPort }) => {
    if (currentCell && currentPort) {
      currentCell.setPortProp(currentPort, 'attrs/circle/fill', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/stroke', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/style/visibility', 'visible');
    }
    // 更新连接桩标签
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('edge:removed', () => {
    updateAllEdgeLabels();
  });

  graph.on('edge:change:source', ({ edge }) => {
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('edge:change:target', ({ edge }) => {
    if (edge) applyEdgeLabel(edge);
  });

  graph.on('node:change:position', () => {
    syncUnsavedState();
  });

  graph.on('node:added', () => {
    syncUnsavedState();
  });

  graph.on('node:removed', () => {
    hasNodes.value = graph.getNodes().length > 0;
    syncUnsavedState();
  });

  graph.on('edge:added', () => {
    syncUnsavedState();
  });

  graph.on('edge:removed', () => {
    hasNodes.value = graph.getNodes().length > 0;
    syncUnsavedState();
  });

  // 节点双击编辑（冻结状态下可以查看但不能更改）
  // 节点单击：选择节点并在右侧边栏显示
  graph.on('node:click', ({ node }) => {
    selectNode(node.id);
  });

  // 节点双击：选择节点并自动展开右侧边栏
  graph.on('node:dblclick', ({ node }) => {
    selectNode(node.id);
    sidebarExpanded.value = true;
  });

  // 订阅 sessionStore 变化，更新节点绑定状态显示
  unsubscribeSessionStore = sessionStore.subscribe((state) => {
    console.log('[GraphEditor] Session store updated, viewBindings:', state.mappings?.viewBindings);
    // 当视图绑定变化时，更新所有 OSC 和 SPECTRUM 节点的标签
    graph.getNodes().forEach((node) => {
      const data = node.getData() as GraphNode;
      if (data && (data.type === 'OSC' || data.type === 'SPECTRUM')) {
        const labelText = generateNodeLabel(data.type, data.name, data.params, node.id);
        console.log('[GraphEditor] Updating node label:', node.id, labelText);
        node.attr('label/text', labelText);
      }
    });
  });

  // 加载数据
  await nextTick();
  await loadFromBackend();
  
  // 启动运行时状态轮询
  startRuntimeStatePolling();
});

onUnmounted(() => {
  window.removeEventListener('keydown', onSaveHotkey);
  window.removeEventListener('beforeunload', onBeforeUnload);

  stopMockDataStream();
  stopRuntimeStatePolling();
  stopEdgeAnimations();
  
  // 保存当前状态到会话存储
  saveStateToSessionStorage();
  
  graphRef.value?.dispose();
  // 取消订阅
  unsubscribeSessionStore?.();
  unsubscribeGraphSync?.();
  graphSyncWebSocket.disconnect();
});
</script>

<style scoped>
.fullscreen-graph-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fafafa;
  min-height: 0; /* 确保flex容器可以收缩 */
}

.graph-toolbar {
  flex-shrink: 0;
  border-bottom: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.graph-content {
  flex: 1;
  padding: 16px;
  overflow: hidden; /* 改为hidden，让内部容器处理滚动 */
  min-height: 0; /* 确保flex容器可以收缩 */
  display: flex;
  flex-direction: column;
}

.graph-wrapper {
  display: flex;
  flex: 1;
  min-height: 0; /* 确保flex容器可以收缩 */
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  position: relative;
}

.palette {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e0e0e0;
  background: #fff;
  overflow-y: auto; /* 改为垂直滚动 */
  overflow-x: hidden;
  min-height: 0;
}

.palette-title {
  padding: 16px;
  font-weight: 600;
  font-size: 14px;
  color: #333;
  border-bottom: 1px solid #e0e0e0;
}

.palette-group {
  border-bottom: 1px solid #e0e0e0;
}

.group-title {
  padding: 12px 16px;
  font-size: 12px;
  color: #666;
  background: #fafafa;
  font-weight: 500;
}

.palette-item {
  padding: 12px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: grab;
  transition: background 0.2s;
  border-bottom: 1px solid #f0f0f0;
}

.palette-item:hover {
  background: #f5f5f5;
}

.palette-item:active {
  cursor: grabbing;
}

.palette-item-disabled {
  opacity: 0.5;
  cursor: not-allowed !important;
  background: #f9f9f9 !important;
}

.palette-item-disabled:hover {
  background: #f9f9f9 !important;
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
  font-size: 14px;
  color: #333;
}

.graph-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #fafafa;
  position: relative;
}

.graph-hint {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #90a4ae;
  pointer-events: none;
}

.hint-text {
  font-size: 16px;
  margin-top: 8px;
  color: #607d8b;
}

.hint-sub {
  font-size: 13px;
  margin-top: 4px;
}

/* 右侧边栏样式 */
.sidebar {
  width: 400px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e0e0e0;
  background: #fff;
  transition: width 0.3s ease;
  overflow: hidden;
  min-height: 0; /* 确保flex容器可以收缩 */
}

.sidebar-collapsed {
  width: 40px;
}

.sidebar-header {
  display: flex;
  align-items: center;
  padding: 12px;
  border-bottom: 1px solid #e0e0e0;
  background: #fafafa;
  min-height: 56px;
}

.sidebar-toggle {
  margin-right: 8px;
}

.sidebar-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
  display: flex;
  align-items: center;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.sidebar-node-edit {
  height: 100%;
}

/* NodeEditDialog 边栏模式样式 */
.node-edit-sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.node-edit-sidebar .sidebar-header {
  padding: 16px;
  background: #fff;
  border-bottom: 1px solid #e0e0e0;
}

.node-edit-sidebar .sidebar-title {
  font-size: 16px;
  font-weight: 600;
}

.node-edit-sidebar .sidebar-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.node-edit-sidebar .sidebar-actions {
  padding: 16px;
  background: #fafafa;
  border-top: 1px solid #e0e0e0;
}

.node-edit-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 确保表单内容可滚动 */
.node-edit-content .v-card-text {
  flex: 1;
  overflow-y: auto;
  padding: 16px !important;
}

/* 调整画布容器宽度 */
.graph-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 确保flex容器可以收缩 */
  background: #fafafa;
  position: relative;
  transition: width 0.3s ease;
  overflow: auto; /* 添加滚动 */
}

/* 确保X6画布充分利用空间 */
.x6-graph {
  flex: 1;
  min-height: 0;
  width: 100%;
  height: 100%;
}

.x6-graph-scroller {
  width: 100% !important;
  height: 100% !important;
  overflow: auto !important;
}

.x6-graph-background {
  width: 100% !important;
  height: 100% !important;
}

.x6-graph-svg {
  width: 100% !important;
  height: 100% !important;
}

/* 响应式调整 */
@media (max-width: 1200px) {
  .sidebar {
    width: 350px;
  }
  
  .sidebar-collapsed {
    width: 40px;
  }
}

@media (max-width: 960px) {
  .sidebar {
    width: 300px;
  }
  
  .palette {
    width: 180px;
  }
}
</style>
