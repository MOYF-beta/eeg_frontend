<template>
  <ViewContainer>
    <v-container fluid class="py-4">
    <div class="d-flex align-center justify-space-between mb-4">
      <h1 class="text-h5">波形可视化</h1>
      
      <div class="d-flex align-center gap-2">
        <div class="text-caption text-grey mr-1">布局网格:</div>
        <v-btn-toggle v-model="gridColumns" mandatory density="compact" class="mr-2">
          <v-btn :value="1" size="small">1x1</v-btn>
          <v-btn :value="2" size="small">2x2</v-btn>
          <v-btn :value="3" size="small">3x3</v-btn>
          <v-btn :value="4" size="small">4x4</v-btn>
        </v-btn-toggle>

        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          size="small"
          @click="addOscilloscope"
          :disabled="!canAddOscilloscope"
        >
          添加示波器
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-plus"
          size="small"
          @click="addSpectrum"
          :disabled="!canAddSpectrum"
        >
          添加频谱
        </v-btn>
        <v-btn
          color="info"
          prepend-icon="mdi-plus"
          size="small"
          @click="addTopoMap"
          :disabled="!canAddTopoMap"
        >
          添加10-20可视化
        </v-btn>
      </div>
    </div>

    <!-- 提示信息 -->
    <v-alert v-if="!hasOscNodes && !hasSpectrumNodes" type="info" class="mb-4">
      计算图中没有示波器或频谱节点。
      <router-link to="/cpgraph">前往计算图编辑器添加 →</router-link>
    </v-alert>

    <!-- 可视化组件网格 -->
    <div class="visualization-grid" :style="{ '--grid-cols': gridColumns }">
      <!-- 示波器卡片列表 -->
      <div v-for="(osc, index) in oscilloscopes" :key="osc.id" class="grid-item">
        <Oscilloscope
          :initial-node-id="osc.initialNodeId"
          @remove="removeOscilloscope(index)"
        />
      </div>

      <!-- 频谱卡片列表 -->
      <div v-for="(spec, index) in spectrums" :key="spec.id" class="grid-item">
        <FrequencyView
          :initial-node-id="spec.initialNodeId"
          @remove="removeSpectrum(index)"
        />
      </div>

      <!-- 10-20 脑地形图卡片列表 -->
      <div v-for="(topo, index) in topoMaps" :key="topo.id" class="grid-item">
        <TenTwentyTopoMap
          :initial-node-id="topo.initialNodeId"
          @remove="removeTopoMap(index)"
        />
      </div>
    </div>

    <!-- 空状态 -->
    <v-card v-if="oscilloscopes.length === 0 && spectrums.length === 0 && topoMaps.length === 0" variant="outlined" class="pa-8 text-center">
      <v-icon size="64" color="grey-lighten-2">mdi-waveform</v-icon>
      <div class="text-h6 mt-4 text-grey">暂无可视化组件</div>
      <div class="text-body-2 text-grey mt-2">
        点击上方按钮添加示波器或频谱分析组件
      </div>
    </v-card>
  </v-container>
  </ViewContainer>
</template>

<script setup lang="ts">
import ViewContainer from '../components/ViewContainer.vue';
import { ref, computed, onMounted, watch } from 'vue';
import Oscilloscope from '../components/Oscilloscope.vue';
import FrequencyView from '../components/FrequencyView.vue';
import TenTwentyTopoMap from '../components/TenTwentyTopoMap.vue';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';

// ========== localStorage 持久化 ==========
const STORAGE_KEY = 'viz_layout_settings';

interface VizLayout {
  gridColumns: number;
  oscilloscopes: ViewerItem[];
  spectrums: ViewerItem[];
  topoMaps: ViewerItem[];
}

const loadLayout = (): VizLayout | null => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data && typeof data.gridColumns === 'number' && Array.isArray(data.oscilloscopes) && Array.isArray(data.spectrums)) {
      if (!Array.isArray(data.topoMaps)) data.topoMaps = [];
      return data as VizLayout;
    }
  } catch (e) {
    console.warn('[VisualizationView] Failed to load layout:', e);
  }
  return null;
};

let saveTimer: ReturnType<typeof setTimeout> | null = null;
const saveLayout = () => {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      const data: VizLayout = {
        gridColumns: gridColumns.value,
        oscilloscopes: oscilloscopes.value.map(o => ({ id: o.id, initialNodeId: o.initialNodeId })),
        spectrums: spectrums.value.map(s => ({ id: s.id, initialNodeId: s.initialNodeId })),
        topoMaps: topoMaps.value.map(t => ({ id: t.id, initialNodeId: t.initialNodeId })),
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn('[VisualizationView] Failed to save layout:', e);
    }
    saveTimer = null;
  }, 300);
};

// 计算图节点
const graphNodes = ref<GraphNode[]>([]);

// 网格布局显示模式
const gridColumns = ref(1);

// 示波器列表
interface ViewerItem {
  id: string;
  initialNodeId?: string;
}

const oscilloscopes = ref<ViewerItem[]>([]);
const spectrums = ref<ViewerItem[]>([]);
const topoMaps = ref<ViewerItem[]>([]);

// 计算属性
const oscNodes = computed(() => graphNodes.value.filter(n => n.type === 'OSC'));
const spectrumNodes = computed(() => graphNodes.value.filter(n => n.type === 'SPECTRUM'));
const hasOscNodes = computed(() => oscNodes.value.length > 0);
const hasSpectrumNodes = computed(() => spectrumNodes.value.length > 0);

// 检查是否可以添加更多示波器（每个OSC节点对应一个）
const canAddOscilloscope = computed(() => {
  return oscNodes.value.length > oscilloscopes.value.length;
});

const canAddSpectrum = computed(() => {
  // SPECTRUM节点或OSC节点都可以作为频谱数据源
  const availableNodes = graphNodes.value.filter(n => n.type === 'SPECTRUM' || n.type === 'OSC');
  return availableNodes.length > spectrums.value.length;
});

const canAddTopoMap = computed(() => {
  // OSC 或 SPECTRUM 节点都可以作为 10-20 可视化的数据源
  const availableNodes = graphNodes.value.filter(n => n.type === 'OSC' || n.type === 'SPECTRUM');
  return availableNodes.length > topoMaps.value.length;
});

// 方法
const addOscilloscope = () => {
  // 找到未使用的OSC节点
  const usedNodeIds = new Set(oscilloscopes.value.map(o => o.initialNodeId).filter(Boolean));
  const availableNode = oscNodes.value.find(n => !usedNodeIds.has(n.id));
  
  oscilloscopes.value.push({
    id: 'osc-' + Date.now(),
    initialNodeId: availableNode?.id,
  });
};

const addSpectrum = () => {
  // 找到未使用的SPECTRUM或OSC节点
  const usedNodeIds = new Set(spectrums.value.map(s => s.initialNodeId).filter(Boolean));
  const availableNodes = graphNodes.value.filter(n => 
    (n.type === 'SPECTRUM' || n.type === 'OSC') && !usedNodeIds.has(n.id)
  );
  const availableNode = availableNodes[0];
  
  spectrums.value.push({
    id: 'spectrum-' + Date.now(),
    initialNodeId: availableNode?.id,
  });
};

const removeOscilloscope = (index: number) => {
  oscilloscopes.value.splice(index, 1);
};

const removeSpectrum = (index: number) => {
  spectrums.value.splice(index, 1);
};

const addTopoMap = () => {
  const usedNodeIds = new Set(topoMaps.value.map(t => t.initialNodeId).filter(Boolean));
  const availableNodes = graphNodes.value.filter(n =>
    (n.type === 'OSC' || n.type === 'SPECTRUM') && !usedNodeIds.has(n.id)
  );
  const availableNode = availableNodes[0];

  topoMaps.value.push({
    id: 'topo-' + Date.now(),
    initialNodeId: availableNode?.id,
  });
};

const removeTopoMap = (index: number) => {
  topoMaps.value.splice(index, 1);
};

// 加载计算图
const loadGraph = async () => {
  try {
    const graph = await fetchGraph();
    graphNodes.value = graph.nodes || [];
  } catch (e) {
    console.error('Failed to load graph:', e);
  }
};

onMounted(() => {
  loadGraph();
  
  // 恢复保存的布局
  const savedLayout = loadLayout();
  if (savedLayout && (savedLayout.oscilloscopes.length > 0 || savedLayout.spectrums.length > 0 || savedLayout.topoMaps.length > 0)) {
    gridColumns.value = savedLayout.gridColumns;
    oscilloscopes.value = savedLayout.oscilloscopes;
    spectrums.value = savedLayout.spectrums;
    topoMaps.value = savedLayout.topoMaps || [];
    return;
  }

  // 默认添加一个示波器和一个频谱（如果有节点）
  setTimeout(() => {
    if (hasOscNodes.value && oscilloscopes.value.length === 0) {
      addOscilloscope();
    }
    if ((hasSpectrumNodes.value || hasOscNodes.value) && spectrums.value.length === 0) {
      addSpectrum();
    }
  }, 500);
});

// 监听布局变化自动保存
watch(gridColumns, () => saveLayout());
watch(oscilloscopes, () => saveLayout(), { deep: true });
watch(spectrums, () => saveLayout(), { deep: true });
watch(topoMaps, () => saveLayout(), { deep: true });
</script>

<style scoped>
.visualization-grid {
  display: grid;
  grid-template-columns: repeat(var(--grid-cols), 1fr);
  gap: 16px;
  align-items: start;
}

.grid-item {
  min-width: 0; /* 防止内容撑开网格 */
}

.gap-2 {
  gap: 8px;
}
</style>
