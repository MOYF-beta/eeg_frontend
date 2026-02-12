<template>
  <v-container class="py-6">
    <div class="d-flex align-center justify-space-between mb-6">
      <h1 class="text-h4">波形可视化</h1>
      
      <div class="d-flex gap-2">
        <v-btn
          color="primary"
          prepend-icon="mdi-plus"
          @click="addOscilloscope"
          :disabled="!canAddOscilloscope"
        >
          添加示波器
        </v-btn>
        <v-btn
          color="secondary"
          prepend-icon="mdi-plus"
          @click="addSpectrum"
          :disabled="!canAddSpectrum"
        >
          添加频谱
        </v-btn>
      </div>
    </div>

    <!-- 提示信息 -->
    <v-alert v-if="!hasOscNodes && !hasSpectrumNodes" type="info" class="mb-4">
      计算图中没有示波器或频谱节点。
      <a href="#/cpgraph">前往计算图编辑器添加 →</a>
    </v-alert>

    <!-- 示波器卡片列表 -->
    <div v-for="(osc, index) in oscilloscopes" :key="osc.id">
      <Oscilloscope
        :initial-node-id="osc.initialNodeId"
        @remove="removeOscilloscope(index)"
      />
    </div>

    <!-- 频谱卡片列表 -->
    <div v-for="(spec, index) in spectrums" :key="spec.id">
      <SpectrumViewer
        :initial-node-id="spec.initialNodeId"
        @remove="removeSpectrum(index)"
      />
    </div>

    <!-- 空状态 -->
    <v-card v-if="oscilloscopes.length === 0 && spectrums.length === 0" variant="outlined" class="pa-8 text-center">
      <v-icon size="64" color="grey-lighten-2">mdi-waveform</v-icon>
      <div class="text-h6 mt-4 text-grey">暂无可视化组件</div>
      <div class="text-body-2 text-grey mt-2">
        点击上方按钮添加示波器或频谱分析组件
      </div>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import Oscilloscope from '../components/Oscilloscope.vue';
import SpectrumViewer from '../components/SpectrumViewer.vue';
import { fetchGraph } from '../services/graph';
import type { GraphNode } from '../services/graph';

// 计算图节点
const graphNodes = ref<GraphNode[]>([]);

// 示波器列表
interface ViewerItem {
  id: string;
  initialNodeId?: string;
}

const oscilloscopes = ref<ViewerItem[]>([]);
const spectrums = ref<ViewerItem[]>([]);

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
</script>

<style scoped>
.gap-2 {
  gap: 8px;
}
</style>
