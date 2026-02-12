import { createRouter, createWebHistory } from 'vue-router';
import DevicesView from '../views/DevicesView.vue';
import OscilloscopeView from '../views/OscilloscopeView.vue';
import VisualizationView from '../views/VisualizationView.vue';
import CpgraphView from '../views/CpgraphView.vue';
import TestView from '../views/TestView.vue';

const routes = [
  { path: '/', redirect: '/devices' },
  { path: '/devices', name: 'Devices', component: DevicesView },
  { path: '/oscilloscope', name: 'Oscilloscope', component: OscilloscopeView },
  { path: '/visualization', name: 'Visualization', component: VisualizationView },
  { path: '/cpgraph', name: 'Cpgraph', component: CpgraphView },
  { path: '/test', name: 'Test', component: TestView },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
