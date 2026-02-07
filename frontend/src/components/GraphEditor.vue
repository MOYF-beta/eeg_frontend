<template>
  <v-card class="mb-4" variant="tonal">
      <v-card-title class="d-flex align-center justify-space-between">
      计算图编辑器
      <div class="d-flex align-center ga-2">
        <v-switch v-model="frozen" density="compact" hide-details label="冻结" />
        <v-btn size="small" variant="tonal" @click="save">保存</v-btn>
        <v-btn size="small" color="primary" @click="run" :disabled="!frozen">运行</v-btn>
        <v-switch v-model="debug" density="compact" hide-details label="调试" />
      </div>
    </v-card-title>
    <v-divider />
    <v-card-text>
      <div class="graph-layout">
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
              {{ item.title }}
            </div>
          </div>
        </div>

        <div class="graph-wrap">
          <div ref="container" class="graph"></div>
          <div
            v-if="editing"
            class="node-editor"
            :style="{ left: `${editorLeft}px`, top: `${editorTop}px`, width: `${editorWidth}px` }"
          >
            <div class="node-editor-title">编辑节点</div>
            <v-text-field
              v-model="editingName"
              label="名称"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-textarea
              v-model="editingParams"
              label="参数 (JSON)"
              density="compact"
              variant="outlined"
              rows="4"
              hide-details
            />
            <div class="node-editor-actions">
              <v-btn size="small" variant="tonal" @click="cancelEdit">取消</v-btn>
              <v-btn size="small" color="primary" @click="commitEdit">应用</v-btn>
            </div>
          </div>
        </div>
        <div class="side-panel">
          <div class="panel-title">节点参数</div>
          <div v-if="activeNode" class="panel-body">
            <v-text-field
              v-model="activeNodeName"
              label="名称"
              density="compact"
              variant="outlined"
              hide-details
            />
            <v-textarea
              v-model="activeNodeParams"
              label="参数 (JSON)"
              density="compact"
              variant="outlined"
              rows="6"
              hide-details
            />
            <v-btn size="small" variant="tonal" @click="applyNodeParams" :disabled="frozen">
              应用
            </v-btn>
          </div>
          <div v-else class="panel-empty">选择一个节点以编辑参数或双击节点</div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';
import { Graph } from '@antv/x6';
import { Dnd } from '@antv/x6-plugin-dnd';
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
const activeNode = ref<GraphNode | null>(null);
const activeNodeName = ref('');
const activeNodeParams = ref('{}');
const debug = ref(false);
const editing = ref(false);
const editingNodeId = ref<string | null>(null);
const editingName = ref('');
const editingParams = ref('{}');
const editorLeft = ref(0);
const editorTop = ref(0);
const editorWidth = ref(220);

const typeItems: Array<{ title: string; value: GraphNodeType }> = [
  { title: '数据源', value: 'SOURCE' },
  { title: '回放', value: 'REPLAY' },
  { title: '滤波器', value: 'FILTER' },
  { title: '求和器', value: 'SUM' },
  { title: '通道分离器', value: 'SPLIT' },
  { title: '通道合并器', value: 'MERGE' },
  { title: '示波器', value: 'OSC' },
  { title: '频谱显示器', value: 'SPECTRUM' },
  { title: '保存节点', value: 'SAVE' },
];

const typeColors: Record<GraphNodeType, string> = {
  SOURCE: '#E3F2FD',
  REPLAY: '#E3F2FD',
  FILTER: '#E8F5E9',
  SUM: '#F3E5F5',
  SPLIT: '#FFFDE7',
  MERGE: '#FFF3E0',
  OSC: '#E0F2F1',
  SPECTRUM: '#E8EAF6',
  SAVE: '#FCE4EC',
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
        r: 5,
        magnet: true,
        stroke: '#90A4AE',
        strokeWidth: 1,
        fill: '#ffffff',
        style: { visibility: 'hidden' },
      },
    },
  },
  out: {
    position: {
      name: 'right',
      args: { dx: -8 },
    },
    attrs: {
      circle: {
        r: 5,
        magnet: true,
        stroke: '#90A4AE',
        strokeWidth: 1,
        fill: '#ffffff',
        style: { visibility: 'hidden' },
      },
    },
  },
};

const buildPayload = (): GraphPayload => {
  const graph = graphRef.value;
  if (!graph) return { nodes: [], edges: [], frozen: frozen.value };
  const nodes: GraphNode[] = graph.getNodes().map((node) => {
    const data = (node.getData() || {}) as GraphNode;
    const { x, y } = node.position();
    return {
      id: node.id,
      type: data.type,
      name: data.name,
      x,
      y,
      params: data.params || {},
    };
  });
  const edges = graph.getEdges().map((edge) => ({
    id: edge.id,
    source: edge.getSourceCellId() || '',
    target: edge.getTargetCellId() || '',
  }));
  return { nodes, edges, frozen: frozen.value };
};

const syncSelection = (node: GraphNode | null) => {
  activeNode.value = node;
  activeNodeName.value = node?.name || '';
  activeNodeParams.value = JSON.stringify(node?.params || {}, null, 2);
};

const createNode = (type: GraphNodeType) => {
  const id = `node-${Date.now()}-${Math.floor(Math.random() * 1000)}`;
  const name = typeItems.find((i) => i.value === type)?.title || type;
  return {
    id,
    shape: 'rect',
    width: 160,
    height: 48,
    label: name,
    attrs: {
      body: { fill: typeColors[type], stroke: '#90A4AE', rx: 6, ry: 6 },
      label: { fontSize: 12, fill: '#37474f' },
    },
    ports: { groups: portGroups, items: getPortsByType(type, id) },
    data: { id, type, name, params: {} },
  };
};

const startDrag = (event: MouseEvent, type: GraphNodeType) => {
  if (frozen.value) return;
  const graph = graphRef.value;
  const dnd = dndRef.value;
  if (!graph || !dnd) return;
  const node = graph.createNode(createNode(type));
  dnd.start(node, event);
};

const applyNodeParams = () => {
  const graph = graphRef.value;
  if (!graph || !activeNode.value) return;
  let params = {};
  try {
    params = JSON.parse(activeNodeParams.value || '{}');
  } catch {
    return;
  }
  const node = graph.getCellById(activeNode.value.id);
  if (node && node.isNode()) {
    node.setData({
      ...activeNode.value,
      name: activeNodeName.value,
      params,
    });
    node.attr('label/text', activeNodeName.value);
    syncSelection({
      ...activeNode.value,
      name: activeNodeName.value,
      params,
    });
  }
};

const openEditor = (nodeId: string) => {
  const graph = graphRef.value;
  if (!graph) return;
  const node = graph.getCellById(nodeId);
  if (!node || !node.isNode()) return;
  const data = (node.getData() || {}) as GraphNode;
  editingNodeId.value = nodeId;
  editingName.value = data.name || '';
  editingParams.value = JSON.stringify(data.params || {}, null, 2);
  const view = graph.findViewByCell(node);
  const viewRect = view?.container?.getBoundingClientRect();
  const containerRect = graph.container.getBoundingClientRect();
  if (viewRect) {
    editorLeft.value = viewRect.left - containerRect.left;
    editorTop.value = viewRect.top - containerRect.top + 60;
    editorWidth.value = Math.max(viewRect.width, 220);
  }
  editing.value = true;
};

const commitEdit = () => {
  const graph = graphRef.value;
  if (!graph || !editingNodeId.value) return;
  let params = {};
  try {
    params = JSON.parse(editingParams.value || '{}');
  } catch {
    return;
  }
  const node = graph.getCellById(editingNodeId.value);
  if (node && node.isNode()) {
    const data = (node.getData() || {}) as GraphNode;
    const updated = { ...data, name: editingName.value, params };
    node.setData(updated);
    node.attr('label/text', editingName.value);
    syncSelection(updated);
  }
  editing.value = false;
};

const cancelEdit = () => {
  editing.value = false;
};

const save = async () => {
  await saveGraph(buildPayload());
};

const run = async () => {
  await runGraph();
};

const setGraphInteracting = (graph: Graph, enabled: boolean) => {
  // prefer built-in API if available
  // @ts-ignore
  if (typeof (graph as any).setInteracting === 'function') {
    // @ts-ignore
    (graph as any).setInteracting(enabled);
    return;
  }
  // fallback: toggle pointer events on container to prevent user interaction
  try {
    if (graph.container && graph.container instanceof HTMLElement) {
      graph.container.style.pointerEvents = enabled ? '' : 'none';
    }
  } catch (_) {
    // ignore
  }
};

const applyFrozen = async () => {
  const graph = graphRef.value;
  if (!graph) return;
  await setGraphFrozen(frozen.value);
  setGraphInteracting(graph, !frozen.value);
};

onMounted(async () => {
  if (!container.value) return;
  const graph = new Graph({
    container: container.value,
    grid: true,
    background: { color: '#f5f5f5' },
    panning: { enabled: true, eventTypes: ['leftMouseDown'] },
    mousewheel: { enabled: true, modifiers: ['ctrl', 'meta'] },
    connecting: {
      snap: { radius: 16 },
      allowBlank: false,
      allowLoop: false,
      highlight: true,
      createEdge() {
        return graph.createEdge({
          attrs: { line: { stroke: '#90A4AE', strokeWidth: 1.5 } },
        });
      },
      validateConnection({ sourceMagnet, targetMagnet }) {
        if (!sourceMagnet || sourceMagnet.getAttribute('port-group') === 'in') {
          return false;
        }
        if (!targetMagnet || targetMagnet.getAttribute('port-group') !== 'in') {
          return false;
        }
        return true;
      },
    },
  });
  graphRef.value = graph;
  dndRef.value = new Dnd({ target: graph, scaled: false, animation: true });

  graph.on('node:click', ({ node }) => {
    const data = (node.getData() || {}) as GraphNode;
    syncSelection(data);
  });

  graph.on('node:dblclick', ({ node }) => {
    if (!frozen.value) openEditor(node.id);
  });

  graph.on('blank:click', () => {
    syncSelection(null);
    editing.value = false;
  });

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

  const payload = await fetchGraph().catch(() => ({ nodes: [], edges: [], frozen: false }));
  frozen.value = payload.frozen;
  payload.nodes.forEach((node) => {
    graph.addNode({
      id: node.id,
      shape: 'rect',
      x: node.x,
      y: node.y,
      width: 160,
      height: 48,
      label: node.name,
      attrs: {
        body: { fill: typeColors[node.type], stroke: '#90A4AE', rx: 6, ry: 6 },
        label: { fontSize: 12, fill: '#37474f' },
      },
      ports: { groups: portGroups, items: getPortsByType(node.type, node.id) },
      data: node,
    });
  });
  payload.edges.forEach((edge) => {
    graph.addEdge({
      id: edge.id,
      source: { cell: edge.source, port: `${edge.source}-out` },
      target: { cell: edge.target, port: `${edge.target}-in` },
      attrs: { line: { stroke: '#90A4AE', strokeWidth: 1.5 } },
    });
  });

  setGraphInteracting(graph, !frozen.value);
  if (frozen.value) editing.value = false;
});

onUnmounted(() => {
  graphRef.value?.dispose();
});

watch(frozen, () => {
  applyFrozen();
});

watch(debug, async (val) => {
  if (val) {
    const payload = buildPayload();
    try {
      // send debug payload to backend which prints to terminal
      // import lazily to avoid cyclic issues
      const mod = await import('../services/graph');
      await mod.debugGraph(payload);
      // reset switch after sending
      debug.value = false;
    } catch (err) {
      // keep switch off on error
      debug.value = false;
      // optionally log to browser console
      // eslint-disable-next-line no-console
      console.error('debug send failed', err);
    }
  }
});
</script>

<style scoped>
.graph-layout {
  display: grid;
  grid-template-columns: 200px 1fr 260px;
  gap: 16px;
  align-items: stretch;
}
.palette {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
  display: grid;
  gap: 12px;
  max-height: 520px;
  overflow: auto;
}
.palette-title {
  font-weight: 600;
  color: #37474f;
}
.palette-group {
  display: grid;
  gap: 6px;
}
.group-title {
  font-size: 12px;
  color: #78909c;
}
.palette-item {
  padding: 8px 10px;
  border: 1px solid #cfd8dc;
  border-radius: 6px;
  background: #fafafa;
  cursor: grab;
  font-size: 13px;
  color: #37474f;
}
.palette-item:active {
  cursor: grabbing;
}
.graph-wrap {
  position: relative;
}
.graph {
  width: 100%;
  height: 520px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}
.node-editor {
  position: absolute;
  z-index: 10;
  background: #fff;
  border: 1px solid #cfd8dc;
  border-radius: 8px;
  padding: 10px;
  display: grid;
  gap: 8px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}
.node-editor-title {
  font-weight: 600;
  color: #37474f;
  font-size: 13px;
}
.node-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.side-panel {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
  display: grid;
  gap: 12px;
}
.panel-title {
  font-weight: 600;
  color: #455a64;
}
.panel-body {
  display: grid;
  gap: 8px;
}
.panel-empty {
  color: #90a4ae;
  font-size: 13px;
}
</style>
