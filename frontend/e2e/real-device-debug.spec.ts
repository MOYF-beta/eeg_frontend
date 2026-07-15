import { expect, test } from '@playwright/test';

test.describe('真实设备链路调试', () => {
  test('启动采集并等待20秒截图', async ({ page }) => {
    const api = page.request;

    // 0) 清理可能存在的运行态，避免图保存被拒绝
    await api.delete('/api/graph/run/');

    // 1) 启动后端串口模拟器
    const simResp = await api.post('/api/real-devices/simulator/start/', {
      data: { sample_rate: 1000, channels: 8 },
    });
    expect(simResp.ok()).toBeTruthy();
    const simJson = await simResp.json();
    const port = String(simJson?.data?.port || '');
    expect(port.length).toBeGreaterThan(0);

    // 2) 连接并启动采集
    const connectResp = await api.post('/api/real-devices/connect/', {
      data: { port, baudrate: 460800 },
    });
    expect(connectResp.ok()).toBeTruthy();

    const acqResp = await api.post(`/api/real-devices/${encodeURIComponent(port)}/start-acquisition/`);
    expect(acqResp.ok()).toBeTruthy();

    // 3) 找到与该端口关联的设备ID，并写入一张最小调试图
    const devicesResp = await api.get('/api/devices/');
    expect(devicesResp.ok()).toBeTruthy();
    const devicesJson = await devicesResp.json();
    const devices = Array.isArray(devicesJson?.data) ? devicesJson.data : [];
    const realDevice = devices.find((d: any) => String(d?.config?.port || '') === port);
    expect(realDevice).toBeTruthy();
    const deviceId = String(realDevice.id);

    const graph = {
      nodes: [
        {
          id: 'debug-source-1',
          type: 'SOURCE',
          name: '调试数据源',
          x: 100,
          y: 120,
          deviceId,
          params: {
            sourceMode: 'live',
            sampleRate: 1000,
            channels: 8,
            deviceId,
          },
        },
        {
          id: 'debug-osc-1',
          type: 'OUTPUT',
          name: '调试示波器',
          x: 420,
          y: 120,
          params: {
            timeWindow: 5,
            mode: 'scroll',
          },
        },
      ],
      edges: [
        {
          id: 'debug-edge-1',
          source: 'debug-source-1',
          sourcePort: 'out',
          target: 'debug-osc-1',
          targetPort: 'in',
        },
      ],
      frozen: true,
    };

    const saveGraphResp = await api.post('/api/graph/', { data: graph });
    expect(saveGraphResp.ok()).toBeTruthy();

    const freezeResp = await api.post('/api/graph/freeze/', { data: { frozen: true } });
    expect(freezeResp.ok()).toBeTruthy();

    const runResp = await api.post('/api/graph/run/', { data: { mode: 'live' } });
    expect(runResp.ok()).toBeTruthy();

    // 4) 打开示波器页面并绑定调试节点
    await page.goto('/visualization?_t=real-debug');
    await page.waitForLoadState('networkidle');

    // 打开信号源选择对话框
    const sourceBtn = page.locator('button:has-text("信号源:")').first();
    await sourceBtn.click();
    await page.waitForTimeout(500);

    // 选择调试示波器节点
    await page.locator('text=调试示波器').first().click();
    await page.waitForTimeout(1000);

    // 5) 等待20秒采集后截图
    await page.waitForTimeout(20_000);

    await page.screenshot({
      path: 'e2e/screenshots/debug-real-device-20s.png',
      fullPage: true,
    });

    // 6) 读取调试样本，验证链路确实有数据
    const debugResp = await api.get(`/api/real-devices/debug-output/?port=${encodeURIComponent(port)}&count=200`);
    expect(debugResp.ok()).toBeTruthy();
    const debugJson = await debugResp.json();
    const ports = debugJson?.data?.ports || [];
    const first = ports[0] || {};
    const sampleCount = Number(first?.count || 0);
    expect(sampleCount).toBeGreaterThan(0);

    // Cleanup
    await api.delete('/api/graph/run/');
    await api.post(`/api/real-devices/${encodeURIComponent(port)}/disconnect/`);
    await api.post('/api/real-devices/simulator/stop/', { data: { port } });
  });
});
