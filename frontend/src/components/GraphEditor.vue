<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      计算图编辑器
      <div class="d-flex align-center ga-2">
        <v-switch v-model="frozen" density="compact" hide-details label="冻结" />
        <v-btn 
          size="small" 
          :color="isRunning ? 'error' : 'primary'" 
          @click="toggleRun" 
          :disabled="!frozen"
        >
          <v-icon left size="small" class="mr-1">
            {{ isRunning ? 'mdi-stop' : 'mdi-play' }}
          </v-icon>
          {{ isRunning ? '停止' : '运行' }}
        </v-btn>
        <v-chip v-if="isRunning" size="small" color="success" class="ml-1">
          <v-icon size="small" class="mr-1">mdi-check-circle</v-icon>
          运行中
        </v-chip>
        <v-btn size="small" variant="tonal" @click="exportGraph">导出</v-btn>
        <v-btn size="small" variant="tonal" @click="triggerFileLoad">加载</v-btn>
        <v-btn size="small" color="secondary" @click="loadMockData">加载Mock</v-btn>
        <v-btn size="small" color="info" @click="clear">清空</v-btn>
      </div>
    </v-card-title>
    <v-divider />
    <v-card-text>
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
              draggable="true"
              @dragstart="onDragStart($event, node.type)"
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
              draggable="true"
              @dragstart="onDragStart($event, node.type)"
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
              draggable="true"
              @dragstart="onDragStart($event, node.type)"
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
      </div>
    </v-card-text>
  </v-card>

  <!-- 节点编辑对话框 -->
  <v-dialog v-model="editDialog.open" max-width="500">
    <v-card>
      <v-card-title class="d-flex align-center">
        <v-icon class="mr-2" :color="editDialog.config?.color">mdi-cog</v-icon>
        编辑节点: {{ editDialog.nodeName }}
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
          />
        </div>
      </v-card-text>
      <v-divider />
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="editDialog.open = false">取消</v-btn>
        <v-btn color="primary" @click="saveNodeEdit">保存</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <!-- 使用新的 NodeEditDialog 组件 -->
  <NodeEditDialog
    v-model="nodeEditDialogOpen"
    :node-data="editingNode"
    :all-nodes="allNodes"
    :all-edges="allEdges"
    @save="handleNodeSave"
    @bind-oscilloscope="handleBindOscilloscope"
  />

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
import { onMounted, onUnmounted, ref, nextTick, watch } from 'vue';
import { Graph, Snapline } from '@antv/x6';
import {
  fetchGraph,
  runGraph,
  saveGraph,
  setGraphFrozen,
  stopGraph,
  getGraphRuntimeState,
  type GraphNode,
  type GraphNodeType,
  type GraphPayload,
} from '../services/graph';
import { graphRuntime, type EegPacket } from '../services/runtime';
import { sessionStore } from '../services/sessionStore';
import { eegWebSocket } from '../services/websocket';

import NodeEditDialog from './nodes/NodeEditDialog.vue';

const container = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const frozen = ref(false);
const hasNodes = ref(false);
const isRunning = ref(false);
let runtimeStateTimer: number | null = null;

// 运行时状态轮询
async function pollRuntimeState() {
  try {
    const res = await getGraphRuntimeState();
    if (res.ok) {
      isRunning.value = res.state.running;
    }
  } catch (e) {
    console.error('[GraphEditor] Failed to poll runtime state:', e);
  }
}

function startRuntimeStatePolling() {
  if (runtimeStateTimer) return;
  pollRuntimeState();
  runtimeStateTimer = window.setInterval(pollRuntimeState, 2000);
}

function stopRuntimeStatePolling() {
  if (runtimeStateTimer) {
    clearInterval(runtimeStateTimer);
    runtimeStateTimer = null;
  }
}

// 切换运行/停止
async function toggleRun() {
  if (isRunning.value) {
    // 停止
    try {
      await stopGraph();
      graphRuntime.stop();
      stopMockDataStream();
      isRunning.value = false;
      console.log('[GraphEditor] Graph stopped');
    } catch (err) {
      console.error('[GraphEditor] Failed to stop graph:', err);
      alert('停止失败: ' + (err as Error).message);
    }
  } else {
    // 启动
    await run();
  }
}

// 存储 sessionStore 取消订阅函数
let unsubscribeSessionStore: (() => void) | null = null;

// 新增：NodeEditDialog 相关状态
const nodeEditDialogOpen = ref(false);
const editingNode = ref<GraphNode | null>(null);
const allNodes = ref<GraphNode[]>([]);
const allEdges = ref<Array<{id: string; source: string; target: string}>>([]);

// 监听冻结状态变化
watch(frozen, (newVal, oldVal) => {
  if (newVal !== oldVal) {
    console.log(`[GraphEditor] Frozen state changed: ${oldVal} -> ${newVal}`);
    applyFrozen();
  }
});

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
  SUM: [
    { key: 'weights', label: '权重', type: 'text', hint: '各通道权重,逗号分隔', default: '1,1' },
  ],
  SPLIT: [
    { key: 'channelIndices', label: '分离通道', type: 'text', hint: '要分离的通道索引,逗号分隔', default: '0,1,2,3' },
  ],
  MERGE: [
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
};

// 节点类型配置
const nodeTypes: Record<GraphNodeType, { name: string; color: string; bg: string; icon: string; hasInput: boolean; hasOutput: boolean }> = {
  SOURCE: { name: '数据源', color: '#1976D2', bg: '#E3F2FD', icon: 'SRC', hasInput: false, hasOutput: true },
  REPLAY: { name: '回放', color: '#1976D2', bg: '#E3F2FD', icon: 'RPL', hasInput: false, hasOutput: true },
  FILTER: { name: '滤波器', color: '#388E3C', bg: '#E8F5E9', icon: 'FIL', hasInput: true, hasOutput: true },
  SUM: { name: '求和器', color: '#7B1FA2', bg: '#F3E5F5', icon: 'SUM', hasInput: true, hasOutput: true },
  SPLIT: { name: '分离器', color: '#F9A825', bg: '#FFF8E1', icon: 'SPT', hasInput: true, hasOutput: true },
  MERGE: { name: '合并器', color: '#EF6C00', bg: '#FFF3E0', icon: 'MRG', hasInput: true, hasOutput: true },
  OSC: { name: '示波器', color: '#00796B', bg: '#E0F2F1', icon: 'OSC', hasInput: true, hasOutput: false },
  SPECTRUM: { name: '频谱', color: '#3F51B5', bg: '#E8EAF6', icon: 'FFT', hasInput: true, hasOutput: false },
  SAVE: { name: '保存', color: '#C2185B', bg: '#FCE4EC', icon: 'SAV', hasInput: true, hasOutput: false },
};

const sourceNodes = [
  { type: 'SOURCE' as GraphNodeType, name: '数据源', icon: 'SRC', color: '#1976D2', bg: '#E3F2FD' },
  { type: 'REPLAY' as GraphNodeType, name: '回放', icon: 'RPL', color: '#1976D2', bg: '#E3F2FD' },
];

const processNodes = [
  { type: 'FILTER' as GraphNodeType, name: '滤波器', icon: 'FIL', color: '#388E3C', bg: '#E8F5E9' },
  { type: 'SUM' as GraphNodeType, name: '求和器', icon: 'SUM', color: '#7B1FA2', bg: '#F3E5F5' },
  { type: 'SPLIT' as GraphNodeType, name: '分离器', icon: 'SPT', color: '#F9A825', bg: '#FFF8E1' },
  { type: 'MERGE' as GraphNodeType, name: '合并器', icon: 'MRG', color: '#EF6C00', bg: '#FFF3E0' },
];

const outputNodes = [
  { type: 'OSC' as GraphNodeType, name: '示波器', icon: 'OSC', color: '#00796B', bg: '#E0F2F1' },
  { type: 'SPECTRUM' as GraphNodeType, name: '频谱', icon: 'FFT', color: '#3F51B5', bg: '#E8EAF6' },
  { type: 'SAVE' as GraphNodeType, name: '保存', icon: 'SAV', color: '#C2185B', bg: '#FCE4EC' },
];

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
  }));

  // 使用新的对话框
  editingNode.value = { ...data, id: nodeId, x, y };
  nodeEditDialogOpen.value = true;
}

// 处理节点保存
function handleNodeSave({ name, params, deviceId }: { name: string; params: Record<string, unknown>; deviceId?: string | null }) {
  const graph = graphRef.value;
  if (!graph || !editingNode.value) return;

  const node = graph.getCellById(editingNode.value.id);
  if (!node || !node.isNode()) return;

  // 更新节点数据
  const data = node.getData() as GraphNode;
  data.name = name;
  data.params = { ...params };
  if (deviceId !== undefined) {
    data.deviceId = deviceId || undefined;
  }
  node.setData(data);

  // 更新节点标签显示
  const labelText = generateNodeLabel(data.type, data.name, data.params, editingNode.value?.id);
  node.attr('label/text', labelText);
}

// 处理示波器绑定
function handleBindOscilloscope({ nodeId, oscId }: { nodeId: string; oscId: string | null }) {
  if (oscId) {
    sessionStore.bindOutputNode(nodeId, oscId);
  } else {
    sessionStore.unbindOutputNode(nodeId);
  }
}

// 保存节点编辑（旧版，保留兼容性）
function saveNodeEdit() {
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

// 创建端口
function createPorts(type: GraphNodeType) {
  const config = nodeTypes[type];
  const items = [];
  if (config.hasInput) {
    items.push({ id: 'in', group: 'in' });
  }
  if (config.hasOutput) {
    items.push({ id: 'out', group: 'out' });
  }
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
  const nodeParams = { ...defaultParams, ...params };

  // 生成带属性的标签文本
  const labelText = generateNodeLabel(type, name || config.name, nodeParams);

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
    ports: createPorts(type),
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
    default:
      return '';
  }
}

// 拖拽开始
function onDragStart(e: DragEvent, type: GraphNodeType) {
  e.dataTransfer?.setData('node-type', type);
  e.dataTransfer!.effectAllowed = 'copy';
}

// 从后端加载数据
async function loadFromBackend() {
  const graph = graphRef.value;
  if (!graph) return;

  try {
    const payload = await fetchGraph();
    frozen.value = payload.frozen;

    // 先清空画布
    graph.clearCells();

    // 加载节点
    payload.nodes.forEach((node: GraphNode) => {
      if (!node.id) {
        console.warn('Node without id:', node);
        node.id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
      }
      addNode(node.type, node.x, node.y, node.name, node.params, node.id);
    });

    // 加载边 - 确保节点存在后再连接
    payload.edges.forEach((edge) => {
      const sourceNode = graph.getCellById(edge.source);
      const targetNode = graph.getCellById(edge.target);
      if (sourceNode && targetNode) {
        graph.addEdge({
          id: edge.id,
          source: { cell: edge.source, port: 'out' },
          target: { cell: edge.target, port: 'in' },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    hasNodes.value = graph.getNodes().length > 0;
    setGraphInteracting(graph, !frozen.value);
  } catch (err) {
    console.error('Failed to load graph:', err);
    // 加载失败时显示空白画布，不阻塞用户操作
    hasNodes.value = false;
  }
}

function setGraphInteracting(graph: Graph, enabled: boolean) {
  // X6 2.x: 使用 options 配置交互状态
  if (graph) {
    graph.options.interacting = enabled ? {
      nodeMovable: true,
      edgeMovable: true,
      edgeLabelMovable: true,
      arrowheadMovable: true,
      vertexMovable: true,
      vertexAddable: true,
      vertexDeletable: true,
    } : false;
  }
}

async function applyFrozen() {
  const graph = graphRef.value;
  if (!graph) {
    console.warn('[GraphEditor] applyFrozen: graph ref is null');
    return;
  }

  console.log(`[GraphEditor] applyFrozen called, frozen: ${frozen.value}`);

  if (frozen.value) {
    console.log('[GraphEditor] Freezing graph...');
    
    // 先保存当前计算图到 SessionStore
    const payload = buildPayload();
    console.log('[GraphEditor] Built payload for freeze:', payload);
    sessionStore.setGraph(payload);

    // 验证是否可以冻结
    const validation = sessionStore.validateFreeze();
    console.log('[GraphEditor] Freeze validation result:', validation);

    if (!validation.valid) {
      // 验证失败，提示错误并取消冻结
      console.error('[GraphEditor] Freeze validation failed:', validation.errors);
      alert(`无法冻结计算图:\n${validation.errors.join('\n')}`);
      frozen.value = false;
      return;
    }

    // 显示警告信息（如果有）
    if (validation.warnings.length > 0) {
      console.warn('[GraphEditor] Freeze warnings:', validation.warnings);
    }

    // 验证通过，先自动保存到后端
    try {
      console.log('[GraphEditor] Auto-saving graph before freeze...');
      await saveGraph(payload);
      console.log('[GraphEditor] Auto-save successful');
    } catch (err) {
      console.error('[GraphEditor] Auto-save failed:', err);
      alert('自动保存失败，无法冻结计算图');
      frozen.value = false;
      return;
    }

    // 然后冻结并启动 WebSocket
    try {
      console.log('[GraphEditor] Calling setGraphFrozen(true)...');
      await setGraphFrozen(true);
      setGraphInteracting(graph, false);
      
      // 启动 WebSocket 连接
      console.log('[GraphEditor] Connecting WebSocket...');
      eegWebSocket.connect();
      
      console.log('[GraphEditor] 计算图已冻结，WebSocket连接已建立');
    } catch (err) {
      console.error('[GraphEditor] Failed to freeze graph:', err);
      alert('冻结计算图失败，请检查后端连接');
      frozen.value = false;
    }
  } else {
    // 解冻
    console.log('[GraphEditor] Unfreezing graph...');
    try {
      await setGraphFrozen(false);
      setGraphInteracting(graph, true);
      
      // 断开 WebSocket 连接
      eegWebSocket.disconnect();
      
      console.log('[GraphEditor] 计算图已解冻');
    } catch (err) {
      console.error('[GraphEditor] Failed to unfreeze graph:', err);
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
  }));

  return { nodes, edges, frozen: frozen.value };
}

async function save() {
  console.log('[GraphEditor] Save button clicked, frozen:', frozen.value);
  try {
    const payload = buildPayload();
    console.log('[GraphEditor] Saving graph with payload:', payload);
    await saveGraph(payload);
    console.log('[GraphEditor] Graph saved successfully');
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
          source: { cell: edge.source, port: 'out' },
          target: { cell: edge.target, port: 'in' },
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      } else {
        console.warn('Skipping edge with missing nodes:', edge);
      }
    });

    hasNodes.value = graph.getNodes().length > 0;
    frozen.value = payload.frozen || false;
    
    // 保存到后端
    await saveGraph(buildPayload());
    
    console.log('[GraphEditor] Graph loaded from file:', file.name);
    alert('计算图加载成功');
  } catch (err) {
    console.error('[GraphEditor] Failed to load graph from file:', err);
    alert('加载失败: ' + (err as Error).message);
  } finally {
    // 清空 input 以便可以再次选择同一文件
    input.value = '';
  }
}

async function run() {
  console.log('[GraphEditor] Run button clicked, frozen:', frozen.value);
  
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
    const res = await runGraph();
    console.log('[GraphEditor] Graph run API called successfully');
    if (res.ok) {
      isRunning.value = true;
      startRuntimeStatePolling();
    }
  } catch (err) {
    console.error('[GraphEditor] Failed to run graph:', err);
    alert('运行失败: ' + (err as Error).message);
    return;
  }
  
  // 如果没有WebSocket连接，使用模拟数据流（测试模式）
  if (!eegWebSocket.isConnected()) {
    console.log('[GraphEditor] WebSocket not connected, using mock data stream');
    console.log('WebSocket未连接，使用模拟数据流');
    startMockDataStream();
  }
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
  const graph = graphRef.value;
  if (!graph) return;
  
  // 停止运行时
  graphRuntime.stop();
  stopMockDataStream();
  stopRuntimeStatePolling();
  isRunning.value = false;
  
  graph.clearCells();
  hasNodes.value = false;
}

async function loadMockData() {
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
  for (let i = 0; i < nodeIds.length - 1; i++) {
    graph.addEdge({
      source: { cell: nodeIds[i], port: 'out' },
      target: { cell: nodeIds[i + 1], port: 'in' },
      attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
    });
  }

  await saveGraph(buildPayload());
}

onMounted(async () => {
  if (!container.value) return;

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
      createEdge() {
        return graph.createEdge({
          attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
        });
      },
      validateConnection({ sourceMagnet, targetMagnet }) {
        if (!sourceMagnet || sourceMagnet.getAttribute('port-group') === 'in') return false;
        if (!targetMagnet || targetMagnet.getAttribute('port-group') !== 'in') return false;
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

  // 连接成功高亮
  graph.on('edge:connected', ({ currentCell, currentPort }) => {
    if (currentCell && currentPort) {
      currentCell.setPortProp(currentPort, 'attrs/circle/fill', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/stroke', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/style/visibility', 'visible');
    }
  });

  // 节点双击编辑
  graph.on('node:dblclick', ({ node }) => {
    openNodeEditDialog(node.id);
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
  stopMockDataStream();
  stopRuntimeStatePolling();
  graphRuntime.dispose();
  graphRef.value?.dispose();
  // 取消订阅
  unsubscribeSessionStore?.();
});
</script>

<style scoped>
.graph-wrapper {
  display: flex;
  height: 600px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.palette {
  width: 220px;
  height: 100%;
  border-right: 1px solid #e0e0e0;
  background: #fff;
  overflow-y: auto;
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
  height: 100%;
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
</style>
