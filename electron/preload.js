const { contextBridge, ipcRenderer } = require('electron');

// 安全地暴露API给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  // 获取后端URL
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  
  // 重启后端
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  
  // 监听后端状态
  onBackendReady: (callback) => {
    ipcRenderer.on('backend-ready', (event, url) => callback(url));
  },
  
  onBackendError: (callback) => {
    ipcRenderer.on('backend-error', (event, error) => callback(error));
  },
  
  // 移除监听器
  removeAllListeners: (channel) => {
    ipcRenderer.removeAllListeners(channel);
  }
});

// 暴露应用版本信息
contextBridge.exposeInMainWorld('appInfo', {
  version: process.env.npm_package_version || '1.0.0',
  platform: process.platform
});

console.log('[Preload] Electron API exposed');