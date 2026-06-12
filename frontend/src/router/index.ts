import { createRouter, createWebHistory } from 'vue-router';
import DevicesView from '../views/DevicesView.vue';
import VisualizationView from '../views/VisualizationView.vue';
import CpgraphView from '../views/CpgraphView.vue';
import FullscreenView from '../views/FullscreenView.vue';
import SerialDebugView from '../views/SerialDebugView.vue';
import DevHubView from '../views/DevHubView.vue';

const routes = [
  { path: '/', redirect: '/cpgraph' },
  { path: '/devices', name: 'Devices', component: DevicesView },
  { path: '/visualization', name: 'Visualization', component: VisualizationView },
  { path: '/cpgraph', name: 'Cpgraph', component: CpgraphView, meta: { fullHeight: true } },
  { path: '/dev', name: 'DevHub', component: DevHubView },
  { path: '/dev/serial-debug', name: 'SerialDebug', component: SerialDebugView },
  { path: '/serial-debug', redirect: '/dev/serial-debug' },
  {
    path: '/fullscreen/:type/:nodeId',
    name: 'Fullscreen',
    component: FullscreenView,
    props: true
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
