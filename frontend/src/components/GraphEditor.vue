<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      计算图编辑器
      <div class="d-flex align-center ga-2">
        <v-switch v-model="frozen" density="compact" hide-details label="冻结" />
        <v-btn size="small" variant="tonal" @click="save">保存</v-btn>
        <v-btn size="small" color="primary" @click="run" :disabled="!frozen">运行</v-btn>
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
            <div class="hint-sub">连接节点创建数据处理流程</div>
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, nextTick } from 'vue';
import { Graph } from '@antv/x6';
import { Snapline } from '@antv/x6-plugin-snapline';
import {
  fetchGraph,
  runGraph,
  saveGraph,
  setGraphFrozen,
  type GraphNode,
  type GraphNodeType,
  type GraphPayload,
} from '../services/graph';

const container = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const frozen = ref(false);
const hasNodes = ref(false);

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

// 创建节点 HTML
function createNodeHtml(type: GraphNodeType, name: string) {
  const config = nodeTypes[type];
  return `
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
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: 14px; font-weight: 500; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${name}</div>
        <div style="font-size: 11px; color: #999; margin-top: 2px;">${type}</div>
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

// 添加节点
function addNode(type: GraphNodeType, x: number, y: number, name?: string) {
  const graph = graphRef.value;
  if (!graph) return null;
  
  const config = nodeTypes[type];
  const nodeId = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  
  const node = graph.addNode({
    id: nodeId,
    shape: 'html',
    x,
    y,
    width: 180,
    height: 70,
    html: createNodeHtml(type, name || config.name),
    ports: createPorts(type),
    data: { type, name: name || config.name },
  });
  
  hasNodes.value = true;
  return node;
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
    
    payload.nodes.forEach((node: GraphNode) => {
      graph.addNode({
        id: node.id,
        shape: 'html',
        x: node.x,
        y: node.y,
        width: 180,
        height: 70,
        html: createNodeHtml(node.type, node.name),
        ports: createPorts(node.type),
        data: node,
      });
    });
    
    payload.edges.forEach((edge) => {
      graph.addEdge({
        id: edge.id,
        source: { cell: edge.source, port: `${edge.source}-out` },
        target: { cell: edge.target, port: `${edge.target}-in` },
        attrs: { line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' } },
      });
    });
    
    hasNodes.value = graph.getNodes().length > 0;
    setGraphInteracting(graph, !frozen.value);
  } catch (err) {
    console.error('Failed to load graph:', err);
  }
}

function setGraphInteracting(graph: Graph, enabled: boolean) {
  graph.toggleClipboard(enabled);
}

async function applyFrozen() {
  const graph = graphRef.value;
  if (!graph) return;
  await setGraphFrozen(frozen.value);
  setGraphInteracting(graph, !frozen.value);
}

function buildPayload(): GraphPayload {
  const graph = graphRef.value;
  if (!graph) return { nodes: [], edges: [], frozen: frozen.value };
  
  const nodes: GraphNode[] = graph.getNodes().map((node) => {
    const data = node.getData() as GraphNode;
    const { x, y } = node.position();
    return { ...data, x, y };
  });
  
  const edges = graph.getEdges().map((edge) => ({
    id: edge.id,
    source: edge.getSourceCellId() || '',
    target: edge.getTargetCellId() || '',
  }));
  
  return { nodes, edges, frozen: frozen.value };
}

async function save() {
  await saveGraph(buildPayload());
}

async function run() {
  await runGraph();
}

function clear() {
  const graph = graphRef.value;
  if (!graph) return;
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

  // 加载数据
  await nextTick();
  await loadFromBackend();
});

onUnmounted(() => {
  graphRef.value?.dispose();
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
