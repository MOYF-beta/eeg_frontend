import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
  },
  build: {
    minify: 'esbuild',
    esbuildOptions: {
      keepNames: true,  // 保留函数名，防止类方法被压缩
    },
  },
});
