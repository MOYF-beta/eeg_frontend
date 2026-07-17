import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', redirect: '/cpgraph' },
  { path: '/devices', name: 'Devices', component: () => import('../views/DevicesView.vue') },
  { path: '/visualization', name: 'Visualization', component: () => import('../views/VisualizationView.vue') },
  { path: '/cpgraph', name: 'Cpgraph', component: () => import('../views/CpgraphView.vue'), meta: { fullHeight: true } },
  { path: '/dev', name: 'DevHub', component: () => import('../views/DevHubView.vue') },
  { path: '/dev/serial-debug', name: 'SerialDebug', component: () => import('../views/SerialDebugView.vue') },
  { path: '/serial-debug', redirect: '/dev/serial-debug' },
  {
    path: '/fullscreen/:type/:nodeId',
    name: 'Fullscreen',
    component: () => import('../views/FullscreenView.vue'),
    props: true
  },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
