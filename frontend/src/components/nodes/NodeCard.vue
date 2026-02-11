<template>
  <div class="node-card" :class="data.type?.toLowerCase()">
    <div class="node-header">
      <div class="node-icon" :style="{ background: iconBg, color: iconColor }">
        {{ iconText }}
      </div>
      <div class="node-title">{{ data.name || defaultName }}</div>
    </div>
    <div class="node-body">
      <div v-if="data.type === 'FILTER'" class="node-params">
        <span class="param-tag">{{ data.params?.type || '低通' }}</span>
        <span class="param-tag">{{ data.params?.cutoff || '30' }}Hz</span>
      </div>
      <div v-else-if="data.type === 'SOURCE'" class="node-params">
        <span class="param-tag">实时</span>
      </div>
      <div v-else-if="data.type === 'REPLAY'" class="node-params">
        <span class="param-tag">{{ data.params?.file || '未选择' }}</span>
      </div>
      <div v-else class="node-desc">{{ description }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  data: {
    type?: string;
    name?: string;
    params?: Record<string, any>;
  };
}>();

const typeConfig: Record<string, { name: string; icon: string; bg: string; color: string; desc: string }> = {
  SOURCE: { name: '数据源', icon: 'SRC', bg: '#E3F2FD', color: '#1976D2', desc: '实时数据输入' },
  REPLAY: { name: '回放', icon: 'RPL', bg: '#E3F2FD', color: '#1976D2', desc: '文件回放' },
  FILTER: { name: '滤波器', icon: 'FIL', bg: '#E8F5E9', color: '#388E3C', desc: '信号滤波' },
  SUM: { name: '求和器', icon: 'SUM', bg: '#F3E5F5', color: '#7B1FA2', desc: '通道求和' },
  SPLIT: { name: '分离器', icon: 'SPT', bg: '#FFFDE7', color: '#FBC02D', desc: '通道分离' },
  MERGE: { name: '合并器', icon: 'MRG', bg: '#FFF3E0', color: '#F57C00', desc: '通道合并' },
  OSC: { name: '示波器', icon: 'OSC', bg: '#E0F2F1', color: '#00796B', desc: '波形显示' },
  SPECTRUM: { name: '频谱', icon: 'FFT', bg: '#E8EAF6', color: '#303F9F', desc: '频谱显示' },
  SAVE: { name: '保存', icon: 'SAV', bg: '#FCE4EC', color: '#C2185B', desc: '数据保存' },
};

const config = computed(() => typeConfig[props.data.type || 'SOURCE']);
const defaultName = computed(() => config.value?.name || '节点');
const iconText = computed(() => config.value?.icon || 'N');
const iconBg = computed(() => config.value?.bg || '#ECEFF1');
const iconColor = computed(() => config.value?.color || '#546E7A');
const description = computed(() => config.value?.desc || '');
</script>

<style scoped>
.node-card {
  width: 100%;
  height: 100%;
  padding: 8px 12px;
  background: #fff;
  border: 2px solid;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-sizing: border-box;
}

.node-card.source { border-color: #1976D2; }
.node-card.replay { border-color: #1976D2; }
.node-card.filter { border-color: #388E3C; }
.node-card.sum { border-color: #7B1FA2; }
.node-card.split { border-color: #FBC02D; }
.node-card.merge { border-color: #F57C00; }
.node-card.osc { border-color: #00796B; }
.node-card.spectrum { border-color: #303F9F; }
.node-card.save { border-color: #C2185B; }

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
}

.node-title {
  font-size: 13px;
  font-weight: 600;
  color: #263238;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.node-body {
  flex: 1;
}

.node-params {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.param-tag {
  font-size: 10px;
  padding: 2px 6px;
  background: rgba(0,0,0,0.05);
  border-radius: 4px;
  color: #546E7A;
}

.node-desc {
  font-size: 11px;
  color: #78909C;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
