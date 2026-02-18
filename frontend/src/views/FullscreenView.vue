<template>
  <div class="fullscreen-wrap">
    <Oscilloscope
      v-if="type === 'osc'"
      :initial-node-id="nodeId"
      fullscreen
      @remove="goBack"
    />
    <FrequencyView
      v-else-if="type === 'freq'"
      :initial-node-id="nodeId"
      fullscreen
      @remove="goBack"
    />
    <v-alert v-else type="error">
      无效的组件类型: {{ type }}
    </v-alert>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import Oscilloscope from '../components/Oscilloscope.vue';
import FrequencyView from '../components/FrequencyView.vue';

const props = defineProps<{
  type: string;
  nodeId: string;
}>();

const router = useRouter();

const goBack = () => {
  if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/visualization');
  }
};

onMounted(() => {
  // 隐藏导航栏
  document.body.classList.add('is-fullscreen-view');
});

onUnmounted(() => {
  document.body.classList.remove('is-fullscreen-view');
});
</script>

<style scoped>
.fullscreen-wrap {
  width: 100vw;
  height: 100vh;
  background: #f5f5f5;
  padding: 0;
  margin: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 覆盖 v-main 的 padding */
:global(.is-fullscreen-view .v-main) {
  --v-layout-top: 0px !important;
  --v-layout-bottom: 0px !important;
  padding: 0 !important;
}

:global(.is-fullscreen-view .v-app-bar) {
  display: none !important;
}
</style>
