import { createRouter, createWebHistory } from 'vue-router';
import DevicesView from '../views/DevicesView.vue';
import OscilloscopeView from '../views/OscilloscopeView.vue';
import VisualizationView from '../views/VisualizationView.vue';
import CpgraphView from '../views/CpgraphView.vue';
import TestView from '../views/TestView.vue';
import FullscreenView from '../views/FullscreenView.vue';
import SerialDebugView from '../views/SerialDebugView.vue';

const routes = [
  { path: '/', redirect: '/devices' },
  { path: '/devices', name: 'Devices', component: DevicesView },
  { path: '/oscilloscope', name: 'Oscilloscope', component: OscilloscopeView },
  { path: '/visualization', name: 'Visualization', component: VisualizationView },
  { path: '/cpgraph', name: 'Cpgraph', component: CpgraphView },
  { path: '/serial-debug', name: 'SerialDebug', component: SerialDebugView },
  { path: '/test', name: 'Test', component: TestView },
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
