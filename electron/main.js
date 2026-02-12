const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

// 保持窗口对象的全局引用，防止被垃圾回收
let mainWindow;
let backendProcess;

// 后端服务地址
const BACKEND_PORT = 8000;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

// 创建主窗口
function createWindow() {
  console.log('[Electron] Creating main window...');
  
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    title: 'EEG脑电系统',
    icon: path.join(__dirname, '../build/icon.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    show: false, // 先不显示，等加载完成
    backgroundColor: '#f5f5f5'
  });

  // 加载前端页面
  const isDev = process.env.NODE_ENV === 'development';
  
  if (isDev) {
    // 开发模式：加载开发服务器
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // 生产模式：加载打包后的静态文件
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  // 窗口加载完成后显示
  mainWindow.once('ready-to-show', () => {
    console.log('[Electron] Window ready to show');
    mainWindow.show();
    
    // 启动后端服务
    startBackend();
  });

  // 窗口关闭时清理
  mainWindow.on('closed', () => {
    console.log('[Electron] Window closed');
    mainWindow = null;
    stopBackend();
  });
}

// 启动Django后端服务
function startBackend() {
  console.log('[Electron] Starting backend server...');
  
  const isDev = process.env.NODE_ENV === 'development';
  const isPackaged = app.isPackaged;
  
  let pythonPath;
  let backendPath;
  
  if (isPackaged) {
    // 打包后的路径
    pythonPath = path.join(process.resourcesPath, 'backend', 'python', 'python');
    backendPath = path.join(process.resourcesPath, 'backend');
  } else {
    // 开发环境
    pythonPath = 'python3';
    backendPath = path.join(__dirname, '../backend');
  }
  
  console.log(`[Electron] Python: ${pythonPath}`);
  console.log(`[Electron] Backend: ${backendPath}`);
  
  // 启动Django服务
  const options = {
    cwd: backendPath,
    env: {
      ...process.env,
      PYTHONPATH: backendPath,
      DJANGO_SETTINGS_MODULE: 'eeg_backend.settings'
    }
  };
  
  backendProcess = spawn(pythonPath, ['manage.py', 'runserver', `0.0.0.0:${BACKEND_PORT}`], options);
  
  backendProcess.stdout.on('data', (data) => {
    console.log(`[Backend] ${data.toString().trim()}`);
  });
  
  backendProcess.stderr.on('data', (data) => {
    console.error(`[Backend Error] ${data.toString().trim()}`);
  });
  
  backendProcess.on('close', (code) => {
    console.log(`[Backend] Process exited with code ${code}`);
  });
  
  backendProcess.on('error', (err) => {
    console.error('[Backend] Failed to start:', err);
    
    // 显示错误对话框
    if (mainWindow) {
      mainWindow.webContents.send('backend-error', err.message);
    }
  });
  
  // 等待后端启动完成
  setTimeout(() => {
    console.log('[Electron] Backend should be ready');
    if (mainWindow) {
      mainWindow.webContents.send('backend-ready', BACKEND_URL);
    }
  }, 3000);
}

// 停止后端服务
function stopBackend() {
  if (backendProcess) {
    console.log('[Electron] Stopping backend...');
    
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', backendProcess.pid, '/f', '/t']);
    } else {
      backendProcess.kill('SIGTERM');
    }
    
    backendProcess = null;
  }
}

// IPC通信
ipcMain.handle('get-backend-url', () => {
  return BACKEND_URL;
});

ipcMain.handle('restart-backend', async () => {
  stopBackend();
  await new Promise(resolve => setTimeout(resolve, 1000));
  startBackend();
  return BACKEND_URL;
});

// Electron生命周期
disableHardwareAcceleration: true

app.whenReady().then(() => {
  console.log('[Electron] App ready');
  createWindow();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  console.log('[Electron] All windows closed');
  stopBackend();
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  console.log('[Electron] Before quit');
  stopBackend();
});

// 安全策略：防止新窗口打开
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    console.log(`[Electron] Blocked new window: ${navigationUrl}`);
  });
});

console.log('[Electron] Main process loaded');