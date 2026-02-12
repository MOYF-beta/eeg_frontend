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
      <div class="graph-layout">
        <!-- 左侧 Stencil 节点库 -->
        <div ref="stencilContainer" class="stencil-container"></div>
        
        <!-- 右侧画布 -->
        <div ref="container" class="graph-container"></div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { Graph, Node, Edge } from '@antv/x6';
import { Stencil } from '@antv/x6-plugin-stencil';
import { Snapline } from '@antv/x6-plugin-snapline';
import { register } from '@antv/x6-vue-shape';
import NodeCard from './nodes/NodeCard.vue';
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
const stencilContainer = ref<HTMLDivElement | null>(null);
const graphRef = ref<Graph | null>(null);
const stencilRef = ref<Stencil | null>(null);
const frozen = ref(false);

// 注册自定义 Vue 节点
register({
  shape: 'eeg-node',
  width: 180,
  height: 70,
  component: NodeCard,
});

// 节点类型配置
const typeItems = [
  { title: '数据源', value: 'SOURCE' as GraphNodeType, icon: 'SRC', color: '#1976D2', group: 'source' },
  { title: '回放', value: 'REPLAY' as GraphNodeType, icon: 'RPL', color: '#1976D2', group: 'source' },
  { title: '滤波器', value: 'FILTER' as GraphNodeType, icon: 'FIL', color: '#388E3C', group: 'process' },
  { title: '求和器', value: 'SUM' as GraphNodeType, icon: 'SUM', color: '#7B1FA2', group: 'process' },
  { title: '分离器', value: 'SPLIT' as GraphNodeType, icon: 'SPT', color: '#FBC02D', group: 'process' },
  { title: '合并器', value: 'MERGE' as GraphNodeType, icon: 'MRG', color: '#F57C00', group: 'process' },
  { title: '示波器', value: 'OSC' as GraphNodeType, icon: 'OSC', color: '#00796B', group: 'output' },
  { title: '频谱', value: 'SPECTRUM' as GraphNodeType, icon: 'FFT', color: '#303F9F', group: 'output' },
  { title: '保存', value: 'SAVE' as GraphNodeType, icon: 'SAV', color: '#C2185B', group: 'output' },
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

// 创建端口配置
const createPorts = (nodeId: string, type: GraphNodeType) => {
  const items = [];
  
  // 输入端口（除了数据源）
  if (type !== 'SOURCE' && type !== 'REPLAY') {
    items.push({ id: `${nodeId}-in`, group: 'in' });
  }
  
  // 输出端口（除了输出节点）
  if (type !== 'OSC' && type !== 'SPECTRUM' && type !== 'SAVE') {
    items.push({ id: `${nodeId}-out`, group: 'out' });
  }
  
  return {
    groups: {
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
    },
    items,
  };
};

// 创建节点模板
const createNodeTemplate = (type: GraphNodeType) => {
  const item = typeItems.find((i) => i.value === type)!;
  const id = `template-${type}`;
  
  return {
    shape: 'eeg-node',
    width: 180,
    height: 70,
    ports: createPorts(id, type),
    data: {
      id,
      type,
      name: item.title,
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

const run = async () => {
  await runGraph();
};

const clear = () => {
  const graph = graphRef.value;
  if (!graph) return;
  graph.clearCells();
};

const loadMockData = async () => {
  const mockData = {
    nodes: [
      { id: 'node-source-001', type: 'SOURCE', name: '脑电数据源', x: 50, y: 100, params: { device: '模拟设备', sampleRate: 1000 } },
      { id: 'node-filter-001', type: 'FILTER', name: '低通滤波器', x: 300, y: 100, params: { type: '低通', cutoff: 30, order: 4 } },
      { id: 'node-split-001', type: 'SPLIT', name: '通道分离', x: 550, y: 100, params: { groups: '1-4,5-8' } },
      { id: 'node-osc-001', type: 'OSC', name: '波形显示器', x: 800, y: 100, params: { windowSize: 5, channels: '全部通道' } },
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
      ports: createPorts(node.id, node.type),
      data: node,
    });
  });

  // 添加边
  mockData.edges.forEach((edge) => {
    const sourceNode = graph.getCellById(edge.source) as Node;
    const targetNode = graph.getCellById(edge.target) as Node;
    if (!sourceNode || !targetNode) return;

    graph.addEdge({
      id: edge.id,
      source: { cell: edge.source, port: `${edge.source}-out` },
      target: { cell: edge.target, port: `${edge.target}-in` },
      attrs: { line: { stroke: typeColors.FILTER, strokeWidth: 2, targetMarker: 'block' } },
    });
  });
  
  // 保存到后端
  await saveGraph(mockData);
};

const setGraphInteracting = (graph: Graph, enabled: boolean) => {
  graph.toggleClipboard(enabled);
  graph.toggleKeyboard(enabled);
};

const applyFrozen = async () => {
  const graph = graphRef.value;
  if (!graph) return;
  await setGraphFrozen(frozen.value);
  setGraphInteracting(graph, !frozen.value);
};

onMounted(async () => {
  if (!container.value || !stencilContainer.value) return;

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
          attrs: {
            line: { stroke: '#5F95FF', strokeWidth: 2, targetMarker: 'block' },
          },
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
        args: {
          attrs: {
            fill: '#5F95FF',
            stroke: '#5F95FF',
          },
        },
      },
    },
  });

  graphRef.value = graph;

  // 添加对齐线
  graph.use(new Snapline({ enabled: true }));

  // 创建 Stencil
  const stencil = new Stencil({
    title: '节点库',
    target: graph,
    stencilGraphWidth: 220,
    stencilGraphHeight: 600,
    collapsable: true,
    groups: [
      { title: '数据来源', name: 'source' },
      { title: '处理节点', name: 'process' },
      { title: '显示与保存', name: 'output' },
    ],
    layoutOptions: {
      columns: 1,
      columnWidth: 200,
      rowHeight: 80,
      dx: 10,
      dy: 10,
    },
  });

  stencilRef.value = stencil;
  stencilContainer.value.appendChild(stencil.container);

  // 加载节点模板到 Stencil
  const sourceNodes = typeItems.filter((i) => i.group === 'source').map((i) => createNodeTemplate(i.value));
  const processNodes = typeItems.filter((i) => i.group === 'process').map((i) => createNodeTemplate(i.value));
  const outputNodes = typeItems.filter((i) => i.group === 'output').map((i) => createNodeTemplate(i.value));

  stencil.load(sourceNodes, 'source');
  stencil.load(processNodes, 'process');
  stencil.load(outputNodes, 'output');

  // 节点悬停显示端口
  graph.on('node:mouseenter', ({ node }) => {
    node.getPorts().forEach((port) => {
      node.setPortProp(port.id, 'attrs/circle/style/visibility', 'visible');
    });
  });

  graph.on('node:mouseleave', ({ node }) => {
    node.getPorts().forEach((port) => {
      const edges = graph.getConnectedEdges(node);
      const isConnected = edges.some(
        (e) => e.getSourcePortId() === port.id || e.getTargetPortId() === port.id
      );
      node.setPortProp(port.id, 'attrs/circle/style/visibility', isConnected ? 'visible' : 'hidden');
      node.setPortProp(port.id, 'attrs/circle/fill', isConnected ? '#5F95FF' : '#ffffff');
      node.setPortProp(port.id, 'attrs/circle/stroke', isConnected ? '#5F95FF' : '#90A4AE');
    });
  });

  // 边悬停显示删除按钮
  graph.on('edge:mouseenter', ({ edge }) => {
    edge.addTools({ name: 'button-remove', args: { distance: -40 } });
  });

  graph.on('edge:mouseleave', ({ edge }) => {
    edge.removeTools();
  });

  // 连接成功后高亮端口
  graph.on('edge:connected', ({ currentCell, currentPort }) => {
    if (currentCell && currentPort) {
      currentCell.setPortProp(currentPort, 'attrs/circle/fill', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/stroke', '#5F95FF');
      currentCell.setPortProp(currentPort, 'attrs/circle/style/visibility', 'visible');
    }
  });

  // 双击编辑
  graph.on('node:dblclick', ({ node }) => {
    if (frozen.value) return;
    // TODO: 打开编辑对话框
    console.log('Edit node:', node.getData());
  });

  // 加载数据
  try {
    const payload = await fetchGraph();
    frozen.value = payload.frozen;
    
    payload.nodes.forEach((node) => {
      graph.addNode({
        id: node.id,
        shape: 'eeg-node',
        x: node.x,
        y: node.y,
        width: 180,
        height: 70,
        ports: createPorts(node.id, node.type),
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
    
    setGraphInteracting(graph, !frozen.value);
  } catch (err) {
    console.error('Failed to load graph:', err);
  }
});

onUnmounted(() => {
  graphRef.value?.dispose();
  stencilRef.value?.dispose();
});

watch(frozen, () => applyFrozen());
</script>

<style scoped>
.graph-layout {
  display: flex;
  height: 600px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.stencil-container {
  width: 240px;
  height: 100%;
  border-right: 1px solid #e0e0e0;
  background: #fff;
}

.graph-container {
  flex: 1;
  height: 100%;
  background: #fafafa;
}

/* Stencil 样式覆盖 */
:deep(.x6-widget-stencil) {
  background-color: #fff;
}

:deep(.x6-widget-stencil-title) {
  background-color: #f5f5f5;
  font-weight: 600;
}

:deep(.x6-widget-stencil-group-title) {
  background-color: #fafafa !important;
  font-weight: 500;
}
</style>
