<template>
  <v-card class="mb-4" variant="tonal">
    <v-card-title>数据处理流程（基础版）</v-card-title>
    <v-divider />
    <v-card-text>
      <div ref="container" class="graph"></div>
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { Graph } from '@antv/x6';

const container = ref<HTMLDivElement | null>(null);

onMounted(() => {
  if (!container.value) return;
  const graph = new Graph({
    container: container.value,
    background: { color: '#f5f5f5' },
    grid: true,
  });

  const source = graph.addNode({
    x: 40,
    y: 40,
    width: 140,
    height: 48,
    label: '数据源',
    attrs: { body: { fill: '#E3F2FD', stroke: '#64B5F6' } },
  });

  const filter = graph.addNode({
    x: 240,
    y: 40,
    width: 140,
    height: 48,
    label: '滤波器',
    attrs: { body: { fill: '#E8F5E9', stroke: '#66BB6A' } },
  });

  const scope = graph.addNode({
    x: 440,
    y: 40,
    width: 140,
    height: 48,
    label: '示波器',
    attrs: { body: { fill: '#FFF3E0', stroke: '#FFB74D' } },
  });

  graph.addEdge({ source, target: filter });
  graph.addEdge({ source: filter, target: scope });
});
</script>

<style scoped>
.graph {
  width: 100%;
  height: 240px;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
}
</style>
