import { test, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

test.describe('计算图编辑器 - 导出/加载功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
  });

  test('导出计算图为 JSON 文件', async ({ page, context }) => {
    await page.waitForTimeout(1500);
    
    await expect(page.locator('text=调试示波器')).toBeVisible();
    await expect(page.locator('text=滤波器')).toBeVisible();
    
    // 设置下载监听
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("导出")'),
    ]);
    
    // 验证下载文件名
    const downloadPath = await download.path();
    expect(downloadPath).toBeTruthy();
    expect(download.suggestedFilename()).toMatch(/eeg-graph-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}\.json/);
    
    // 验证文件内容是有效的 JSON
    const content = fs.readFileSync(downloadPath!, 'utf-8');
    const graphData = JSON.parse(content);
    
    expect(graphData).toHaveProperty('nodes');
    expect(graphData).toHaveProperty('edges');
    expect(graphData).toHaveProperty('frozen');
    expect(Array.isArray(graphData.nodes)).toBe(true);
    expect(Array.isArray(graphData.edges)).toBe(true);
    expect(graphData.nodes.length).toBeGreaterThan(0);
    
    // 验证节点结构
    const firstNode = graphData.nodes[0];
    expect(firstNode).toHaveProperty('id');
    expect(firstNode).toHaveProperty('type');
    expect(firstNode).toHaveProperty('name');
    expect(firstNode).toHaveProperty('x');
    expect(firstNode).toHaveProperty('y');
    expect(firstNode).toHaveProperty('params');
    
    await page.screenshot({ path: 'e2e/screenshots/10-export-graph.png', fullPage: true });
  });

  test('加载计算图文件', async ({ page }) => {
    // 准备测试用的计算图文件
    const testGraphData = {
      nodes: [
        {
          id: 'test-source-001',
          type: 'SOURCE',
          name: '测试数据源',
          x: 50,
          y: 100,
          params: { sampleRate: 500, channels: 4, deviceId: 'test-device' }
        },
        {
          id: 'test-filter-001',
          type: 'FILTER',
          name: '测试滤波器',
          x: 300,
          y: 100,
          params: { type: 'bandpass', cutoff: 30, order: 4 }
        },
        {
          id: 'test-osc-001',
          type: 'OUTPUT',
          name: '测试示波器',
          x: 550,
          y: 100,
          params: { timeWindow: 3, yScale: 1.5, mode: 'scroll' }
        }
      ],
      edges: [
        { id: 'edge-001', source: 'test-source-001', target: 'test-filter-001' },
        { id: 'edge-002', source: 'test-filter-001', target: 'test-osc-001' }
      ],
      frozen: false
    };
    
    // 创建临时文件
    const tempFile = path.join(__dirname, 'temp-test-graph.json');
    fs.writeFileSync(tempFile, JSON.stringify(testGraphData, null, 2));
    
    // 使用文件选择器加载文件
    const fileInput = page.locator('input#graph-file-input');
    await fileInput.setInputFiles(tempFile);
    
    await page.waitForTimeout(2000);
    
    // 验证加载的节点
    await expect(page.locator('text=测试数据源')).toBeVisible();
    await expect(page.locator('text=测试滤波器')).toBeVisible();
    await expect(page.locator('text=测试示波器')).toBeVisible();
    
    // 截图验证
    await page.screenshot({ path: 'e2e/screenshots/11-load-graph.png', fullPage: true });
    
    // 清理临时文件
    fs.unlinkSync(tempFile);
  });

  test('冻结时自动保存', async ({ page }) => {
    await page.waitForTimeout(1500);
    
    // 验证初始状态 - 运行按钮应该是禁用的
    const runButton = page.locator('button:has-text("运行")');
    await expect(runButton).toBeDisabled();
    
    // 点击冻结开关（由于未绑定设备，应该显示警告）
    await page.click('[role="switch"]');
    await page.waitForTimeout(1000);
    
    // 处理可能的 alert 对话框（冻结验证失败）
    page.on('dialog', async (dialog) => {
      if (dialog.type() === 'alert') {
        await dialog.accept();
      }
    });
    
    await page.waitForTimeout(2000);
    
    await page.screenshot({ path: 'e2e/screenshots/12-freeze-auto-save.png', fullPage: true });
  });

  test('界面按钮变更验证', async ({ page }) => {
    // 验证新按钮存在
    await expect(page.locator('button:has-text("导出")')).toBeVisible();
    
    // 验证保存按钮存在
    const saveButton = page.locator('button:has-text("保存")');
    await expect(saveButton).toBeVisible();
    
    // 验证其他按钮仍然存在
    await expect(page.locator('button:has-text("运行")')).toBeVisible();
    await expect(page.locator('button:has-text("清空")')).toBeVisible();
    
    await page.screenshot({ path: 'e2e/screenshots/13-ui-buttons.png', fullPage: true });
  });

  test('加载无效的 JSON 文件应显示错误', async ({ page }) => {
    // 创建无效的 JSON 文件
    const invalidFile = path.join(__dirname, 'temp-invalid.json');
    fs.writeFileSync(invalidFile, '{ invalid json content');
    
    // 监听 alert 对话框
    page.on('dialog', async (dialog) => {
      expect(dialog.type()).toBe('alert');
      expect(dialog.message()).toContain('加载失败');
      await dialog.accept();
    });
    
    // 尝试加载无效文件
    const fileInput = page.locator('input#graph-file-input');
    await fileInput.setInputFiles(invalidFile);
    
    await page.waitForTimeout(1000);
    
    // 清理
    fs.unlinkSync(invalidFile);
  });

  test('加载格式错误的 JSON 应显示错误', async ({ page }) => {
    // 创建格式正确但结构错误的 JSON 文件
    const badStructureFile = path.join(__dirname, 'temp-bad-structure.json');
    fs.writeFileSync(badStructureFile, JSON.stringify({ foo: 'bar', notNodes: [] }));
    
    // 监听 alert 对话框
    page.on('dialog', async (dialog) => {
      expect(dialog.type()).toBe('alert');
      expect(dialog.message()).toContain('无效的计算图文件格式');
      await dialog.accept();
    });
    
    // 尝试加载文件
    const fileInput = page.locator('input#graph-file-input');
    await fileInput.setInputFiles(badStructureFile);
    
    await page.waitForTimeout(1000);
    
    // 清理
    fs.unlinkSync(badStructureFile);
  });
});

test.describe('完整导出-加载-冻结流程', () => {
  test('端到端导出加载流程', async ({ page }) => {
    // 1. 加载 Mock 数据
    await page.goto('http://localhost:5173/cpgraph?_t=test');
    await page.waitForLoadState('networkidle');
    await page.click('button:has-text("加载Mock")');
    await page.waitForTimeout(1500);
    
    // 2. 导出计算图
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("导出")'),
    ]);
    
    const downloadPath = await download.path();
    
    // 3. 清空计算图
    await page.click('button:has-text("清空")');
    await page.waitForTimeout(1000);
    
    // 验证已清空
    await expect(page.locator('text=脑电数据源')).not.toBeVisible();
    
    // 4. 加载导出的文件
    const fileInput = page.locator('input#graph-file-input');
    await fileInput.setInputFiles(downloadPath!);
    await page.waitForTimeout(2000);
    
    // 5. 验证数据恢复
    await expect(page.locator('text=脑电数据源')).toBeVisible();
    await expect(page.locator('text=低通滤波器')).toBeVisible();
    await expect(page.locator('text=通道分离')).toBeVisible();
    await expect(page.locator('text=波形显示器')).toBeVisible();
    
    // 6. 验证可以冻结（自动保存）
    await page.click('[role="switch"]');
    await page.waitForTimeout(2000);
    
    const runButton = page.locator('button:has-text("运行")');
    await expect(runButton).toBeEnabled();
    
    await page.screenshot({ path: 'e2e/screenshots/14-end-to-end-flow.png', fullPage: true });
  });
});
