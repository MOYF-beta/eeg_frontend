<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title class="d-flex align-center justify-space-between">
      计算图编辑器
      <div class="d-flex align-center ga-2">
        <v-switch v-model="frozen" density="compact" hide-details label="冻结" />
        <v-btn size="small" variant="tonal" @click="save">保存</v-btn>
        <v-btn size="small" color="secondary" @click="loadMockData">加载Mock</v-btn>
        <v-btn size="small" color="primary" @click="run" :disabled="!frozen">运行</v-btn>
        <v-switch v-model="debug" density="compact" hide-details label="调试" />
      </div>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <div class="graph-layout">
        <!-- 左侧节点库 -->
        <div class="palette">
          <div class="palette-title">节点库</div>
          <div class="palette-group">
            <div class="group-title">数据来源</div>
            <div
              v-for="item in typeItems.filter((i) => ['SOURCE', 'REPLAY'].includes(i.value))"
              :key="item.value"
              class="palette-item"
              @mousedown="startDrag($event, item.value)"
            >
              <span class="item-icon" :style="{ background: item.color + '20', color: item.color }">
                {{ item.icon }}
              </span>
              {{ item.title }}
            </div>
          </div>
          <div class="palette-group">
            <div class="group-title">处理节点</div>
            <div
              v-for="item in typeItems.filter((i) => ['FILTER', 'SUM', 'SPLIT', 'MERGE'].includes(i.value))"
              :key="item.value"
              class="palette-item"
              @mousedown="startDrag($event, item.value)"
            >
              <span class="item-icon" :style="{ background: item.color + '20', color: item.color }">
                {{ item.icon }}
              </span>
              {{ item.title }}
            </div>
          </div>
          <div class="palette-group">
            <div class="group-title">显示与保存</div>
            <div
              v-for="item in typeItems.filter((i) => ['OSC', 'SPECTRUM', 'SAVE'].includes(i.value))"
              :key="item.value"
              class="palette-item"
              @mousedown="startDrag($event, item.value)"
            >
              <span class="item-icon" :style="{ background: item.color + '20', color: item.color }">
                {{ item.icon }}
              </span>
              {{ item.title }}
            </div>
          </div>
        </div>

        <!-- 中间画布 -->
        <div class="graph-wrap">
          <div ref="container" class="graph"></div>
          <div class="graph-hint" v-if="!hasNodes">
            <v-icon size="48" color="grey-lighten-2">mdi-graph-outline</v-icon>
            <div class="hint-text">从左侧拖拽节点到此处</div>
            <div class="hint-sub">双击节点编辑属性，拖拽连接端口创建连线</div>
          </div>
        </div>
      </div>
    </v-card-text>

    <!-- 节点编辑对话框 -->
    <NodeEditDialog
      v-model="editDialog.show"
      :node-data="editDialog.nodeData"
      @save="onNodeEditSave"
    />
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, h, render } from 'vue';
import { Graph, Node } from '@antv/x6';
import { Dnd } from '@antv/x6-plugin-dnd';
import { register } from '@antv/x6-vue-shape';
import NodeCard from './nodes/NodeCard.vue';
import NodeEditDialog from './nodes/NodeEditDialog.vue';
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
const dndRef = ref<Dnd | null>(null);
const frozen = ref(false);
const hasNodes = ref(false);
const debug = ref(false);

const editDialog = ref({
  show: false,
  nodeId: null as string | null,
  nodeData: null as GraphNode | null,
});

// 注册自定义 Vue 节点
register({
  shape: 'eeg-node',
  width: 180,
  height: 70,
  component: NodeCard,
});

const typeItems = [
  { title: '数据源', value: 'SOURCE' as GraphNodeType, icon: 'SRC', color: '#1976D2' },
  { title: '回放', value: 'REPLAY' as GraphNodeType, icon: 'RPL', color: '#1976D2' },
  { title: '滤波器', value: 'FILTER' as GraphNodeType, icon: 'FIL', color: '#388E3C' },
  { title: '求和器', value: 'SUM' as GraphNodeType, icon: 'SUM', color: '#7B1FA2' },
  { title: '分离器', value: 'SPLIT' as GraphNodeType, icon: 'SPT', color: '#FBC02D' },
  { title: '合并器', value: 'MERGE' as GraphNodeType, icon: 'MRG', color: '#F57C00' },
  { title: '示波器', value: 'OSC' as GraphNodeType, icon: 'OSC', color: '#00796B' },
  { title: '频谱', value: 'SPECTRUM' as GraphNodeType, icon: 'FFT', color: '#303F9F' },
  { title: '保存', value: 'SAVE' as GraphNodeType, icon: 'SAV', color: '#C2185B' },
];

const typeColors: Record<GraphNodeType, string> = {
  SOURCE: '#1976D2',
  REPLAY: '#1976D2',
  FILTER: '#388E3C',
  SUM: '#7B1FA2',
  SPLIT: '#FBC02D',
  MERGE: '#F57C00',
  OSC: '#00796B',
  SPECTRUM: '#303F9F',
  SAVE: '#C2185B',
};

const getPortsByType = (type: GraphNodeType, nodeId: string) => {
  if (type === 'SOURCE' || type === 'REPLAY') {
    return [{ id: `${nodeId}-out`, group: 'out' }];
  }
  if (type === 'OSC' || type === 'SPECTRUM' || type === 'SAVE') {
    return [{ id: `${nodeId}-in`, group: 'in' }];
  }
  return [
    { id: `${nodeId}-in`, group: 'in' },
    { id: `${nodeId}-out`, group: 'out' },
  ];
};

const portGroups = {
  in: {
    position: 'left',
    attrs: {
      circle: {
        r: 6,
        magnet: true,
        stroke: '#90A4AE',
        strokeWidth: 2,
        fill: '#ffffff',
        style: { visibility: 'hidden' },
      },
    },
  },
  out: {
    position: { name: 'right', args: { dx: -6 } },
    attrs: {
      circle: {
        r: 6,
        magnet: true,
        stroke: '#90A4AE',
        strokeWidth: 2,
        fill: '#ffffff',
        style: { visibility: 'hidden' },
      },
    },
  },
};

const createNode = (type: GraphNodeType) => {
  const id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  const item = typeItems.find((i) => i.value === type);
  return {
    id,
    shape: 'eeg-node',
    width: 180,
    height: 70,
    ports: { groups: portGroups, items: getPortsByType(type, id) },
    data: {
      id,
      type,
      name: item?.title || type,
      params: getDefaultParams(type),
    },
  };
};

const getDefaultParams = (type: GraphNodeType): Record<string, any> => {
  switch (type) {
    case 'FILTER':
      return { type: '低通', cutoff: 30, order: 4 };
    case 'SOURCE':
      return { device: '模拟设备', sampleRate: 1000 };
    case 'REPLAY':
      return { file: '', loop: false };
    case 'SAVE':
      return { filename: 'data.csv', format: 'CSV' };
    case 'SPLIT':
      return { groups: '1-4,5-8' };
    default:
      return {};
  }
};

const startDrag = (event: MouseEvent, type: GraphNodeType) => {
  if (frozen.value) return;
  const graph = graphRef.value;
  const dnd = dndRef.value;
  if (!graph || !dnd) return;
  const node = graph.createNode(createNode(type));
  dnd.start(node, event);
};

const openNodeEditor = (node: Node) => {
  if (frozen.value) return;
  const data = node.getData() as GraphNode;
  editDialog.value.nodeId = node.id;
  editDialog.value.nodeData = data;
  editDialog.value.show = true;
};

const onNodeEditSave = ({ name, params }: { name: string; params: Record<string, any> }) => {
  const graph = graphRef.value;
  if (!graph || !editDialog.value.nodeId) return;
  const node = graph.getCellById(editDialog.value.nodeId);
  if (node && node.isNode()) {
    const data = node.getData() as GraphNode;
    node.setData({ ...data, name, params });
  }
};

const buildPayload = (): GraphPayload => {
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
};

const save = async () => {
  await saveGraph(buildPayload());
};

const loadMockData = () => {
  const mockData = {
    nodes: [
      { id: 'node-source-001', type: 'SOURCE', name: '脑电数据源', x: 50, y: 100, params: { device: '模拟设备', sampleRate: 1000 } },
      { id: 'node-filter-001', type: 'FILTER', name: '低通滤波器', x: 300, y: 100, params: { type: '低通', cutoff: 30, order: 4 } },
      { id: 'node-split-001', type: 'SPLIT', name: '通道分离', x: 550, y: 100, params: { groups: '1-4,5-8' } },
      { id: 'node-osc-001', type: 'OSC', name: '波形显示器', x: 800, y: 100, params: { windowSize: 5, channels: '全部通道' } },
      { id: 'node-save-001', type: 'SAVE', name: '数据保存', x: 800, y: 250, params: { filename: 'output.csv', format: 'CSV' } },
    ],
    edges: [
      { id: 'edge-001', source: 'node-source-001', target: 'node-filter-001' },
      { id: 'edge-002', source: 'node-filter-001', target: 'node-split-001' },
      { id: 'edge-003', source: 'node-split-001', target: 'node-osc-001' },
    ],
    frozen: false
  };
  
  const graph = graphRef.value;
  if (!graph) return;
  
  // 清除现有节点
  graph.clearCells();
  
  // 添加节点
  mockData.nodes.forEach((node) => {
    graph.addNode({
      id: node.id,
      shape: 'eeg-node',
      x: node.x,
      y: node.y,
      width: 180,
      height: 70,
      ports: { groups: portGroups, items: getPortsByType(node.type, node.id) },
      data: node,
    });
  });
  
  // 添加边
  mockData.edges.forEach((edge) => {
    graph.addEdge({
      id: edge.id,
      source: { cell: edge.source, port: `${edge.source}-out` },
      target: { cell: edge.target, port: `${edge.target}-in` },
      attrs: { line: { stroke: typeColors.FILTER, strokeWidth: 2, targetMarker: 'block' } },
    });
  });
  
  hasNodes.value = true;
};

const run = async () => {
  await runGraph();
};

const setGraphInteracting = (graph: Graph, enabled: boolean) => {
  if (graph.container && graph.container instanceof HTMLElement) {
    graph.container.style.pointerEvents = enabled ? '' : 'none';
  }
};

const applyFrozen = async () => {
  const graph = graphRef.value;
  if (!graph) return;
  await setGraphFrozen(frozen.value);
  setGraphInteracting(graph, !frozen.value);
  if (frozen.value) editDialog.value.show = false;
};

onMounted(async () => {
  if (!container.value) return;
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
      highlight: true,
      createEdge() {
        return graph.createEdge({
          attrs: {
            line: { stroke: typeColors.FILTER, strokeWidth: 2, targetMarker: 'block' },
          },
        });
      },
      validateConnection({ sourceMagnet, targetMagnet }) {
        if (!sourceMagnet || sourceMagnet.getAttribute('port-group') === 'in') return false;
        if (!targetMagnet || targetMagnet.getAttribute('port-group') !== 'in') return false;
        return true;
      },
    },
  });
  graphRef.value = graph;
  dndRef.value = new Dnd({ target: graph, scaled: false, animation: true });

  // 双击编辑
  graph.on('node:dblclick', ({ node }) => openNodeEditor(node));
  
  // 点击空白处关闭编辑
  graph.on('blank:click', () => {
    editDialog.value.show = false;
  });

  // 鼠标悬停显示端口
  graph.on('node:mouseenter', ({ node }) => {
    node.getPorts().forEach((port) => {
      node.setPortProp(port.id, 'attrs/circle/style/visibility', 'visible');
    });
  });
  graph.on('node:mouseleave', ({ node }) => {
    node.getPorts().forEach((port) => {
      node.setPortProp(port.id, 'attrs/circle/style/visibility', 'hidden');
    });
  });

  // 边 hover 效果
  graph.on('edge:mouseenter', ({ edge }) => {
    edge.addTools({ name: 'button-remove', args: { distance: -40 } });
  });
  graph.on('edge:mouseleave', ({ edge }) => {
    edge.removeTools();
  });

  // 加载数据
  const payload = await fetchGraph().catch(() => ({ nodes: [], edges: [], frozen: false }));
  frozen.value = payload.frozen;
  payload.nodes.forEach((node) => {
    graph.addNode({
      id: node.id,
      shape: 'eeg-node',
      x: node.x,
      y: node.y,
      width: 180,
      height: 70,
      ports: { groups: portGroups, items: getPortsByType(node.type, node.id) },
      data: node,
    });
  });
  payload.edges.forEach((edge) => {
    graph.addEdge({
      id: edge.id,
      source: { cell: edge.source, port: `${edge.source}-out` },
      target: { cell: edge.target, port: `${edge.target}-in` },
      attrs: { line: { stroke: typeColors.FILTER, strokeWidth: 2, targetMarker: 'block' } },
    });
  });

  hasNodes.value = graph.getNodes().length > 0;
  graph.on('node:added', () => { hasNodes.value = graph.getNodes().length > 0; });
  graph.on('node:removed', () => { hasNodes.value = graph.getNodes().length > 0; });

  setGraphInteracting(graph, !frozen.value);
});

onUnmounted(() => {
  graphRef.value?.dispose();
});

watch(frozen, () => applyFrozen());

watch(debug, async (val) => {
  if (val) {
    try {
      const { debugGraph } = await import('../services/graph');
      await debugGraph(buildPayload());
      debug.value = false;
    } catch (err) {
      debug.value = false;
      console.error('debug send failed', err);
    }
  }
});
</script>

<style scoped>
.graph-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
}

.palette {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 520px;
  overflow: auto;
}

.palette-title {
  font-weight: 600;
  color: #37474f;
  font-size: 14px;
}

.palette-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.group-title {
  font-size: 11px;
  color: #90a4ae;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.palette-item {
  padding: 8px 10px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  background: #fafafa;
  cursor: grab;
  font-size: 13px;
  color: #37474f;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.2s;
}

.palette-item:hover {
  background: #f5f5f5;
  border-color: #bdbdbd;
}

.palette-item:active {
  cursor: grabbing;
}

.item-icon {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 600;
}

.graph-wrap {
  position: relative;
  height: 520px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.graph {
  width: 100%;
  height: 100%;
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
  font-size: 12px;
  margin-top: 4px;
}
</style>
