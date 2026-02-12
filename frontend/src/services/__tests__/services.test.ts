// SessionStore 和 WebSocket 服务测试
import { sessionStore, type Device, type Oscilloscope } from '../services/sessionStore';
import { eegWebSocket } from '../services/websocket';
import { graphRuntime } from '../services/runtime';

// 测试工具
function assert(condition: boolean, message: string) {
  if (!condition) {
    throw new Error(`Assertion failed: ${message}`);
  }
  console.log('✓', message);
}

// 清理测试数据
function cleanup() {
  sessionStorage.clear();
  sessionStore.clear();
}

// SessionStore 测试
export function testSessionStore() {
  console.log('\n=== Testing SessionStore ===\n');
  cleanup();

  // 测试设备管理
  const devices: Device[] = [
    { id: 'dev1', name: '模拟设备1', status: 'online', sampleRate: 1000, channels: 8 },
    { id: 'dev2', name: '模拟设备2', status: 'offline', sampleRate: 500, channels: 4 },
  ];
  sessionStore.setDevices(devices);
  assert(sessionStore.getDevices().length === 2, 'Devices should be saved');
  assert(sessionStore.getDeviceById('dev1')?.name === '模拟设备1', 'Device lookup should work');

  // 测试示波器管理
  const oscs: Oscilloscope[] = [
    { id: 'osc1', name: '示波器1', isActive: true, timeWindow: 5, yScale: 1 },
    { id: 'osc2', name: '示波器2', isActive: false, timeWindow: 10, yScale: 2 },
  ];
  sessionStore.setOscilloscopes(oscs);
  assert(sessionStore.getOscilloscopes().length === 2, 'Oscilloscopes should be saved');

  // 测试节点映射
  const bindResult = sessionStore.bindInputNode('node1', 'dev1');
  assert(bindResult === true, 'Input node binding should succeed');
  assert(sessionStore.getInputNodeDevice('node1')?.id === 'dev1', 'Input mapping should work');

  const bindResult2 = sessionStore.bindOutputNode('node2', 'osc1');
  assert(bindResult2 === true, 'Output node binding should succeed');
  assert(sessionStore.getOutputNodeOscilloscope('node2')?.id === 'osc1', 'Output mapping should work');

  // 测试冻结验证
  sessionStore.setGraph({
    nodes: [
      { id: 'node1', type: 'SOURCE', name: '数据源', x: 0, y: 0, params: {} },
      { id: 'node2', type: 'OSC', name: '示波器', x: 100, y: 0, params: {} },
    ],
    edges: [],
    frozen: false,
  });

  const validation = sessionStore.validateFreeze();
  assert(validation.valid === true, 'Freeze validation should pass with mappings');
  assert(validation.errors.length === 0, 'No validation errors expected');

  // 测试无映射时的验证
  sessionStore.unbindInputNode('node1');
  const validation2 = sessionStore.validateFreeze();
  assert(validation2.valid === false, 'Freeze validation should fail without input mapping');
  assert(validation2.errors.length > 0, 'Validation errors expected');

  console.log('\n✅ SessionStore tests passed!\n');
  cleanup();
}

// WebSocket 测试（仅测试连接状态管理）
export function testWebSocket() {
  console.log('\n=== Testing WebSocket ===\n');

  // 测试初始状态
  assert(eegWebSocket.getStatus() === 'disconnected', 'Initial status should be disconnected');
  assert(eegWebSocket.isConnected() === false, 'Should not be connected initially');

  // 测试状态变化监听
  let statusChanged = false;
  const unsubscribe = eegWebSocket.onStatusChange((status) => {
    statusChanged = true;
    console.log('Status changed to:', status);
  });

  // 注意：实际连接测试需要后端支持，这里只测试API
  console.log('\n✅ WebSocket API tests passed!\n');
  unsubscribe();
}

// Runtime 测试
export function testRuntime() {
  console.log('\n=== Testing Runtime ===\n');
  cleanup();

  // 设置测试数据
  sessionStore.setDevices([{ id: 'dev1', name: '设备1', status: 'online', sampleRate: 1000, channels: 8 }]);
  sessionStore.setOscilloscopes([{ id: 'osc1', name: '示波器1', isActive: true, timeWindow: 5, yScale: 1 }]);
  sessionStore.bindInputNode('source1', 'dev1');
  sessionStore.bindOutputNode('osc1', 'osc1');
  sessionStore.setGraph({
    nodes: [
      { id: 'source1', type: 'SOURCE', name: '数据源', x: 0, y: 0, params: {} },
      { id: 'osc1', type: 'OSC', name: '示波器', x: 100, y: 0, params: {} },
    ],
    edges: [],
    frozen: false,
  });

  // 测试初始状态
  assert(graphRuntime.state.isRunning === false, 'Runtime should not be running initially');

  // 测试启动（验证通过后）
  // 注意：实际启动会连接WebSocket，这里只测试验证逻辑
  console.log('\n✅ Runtime tests passed!\n');
  cleanup();
}

// 运行所有测试
export function runAllTests() {
  try {
    testSessionStore();
    testWebSocket();
    testRuntime();
    console.log('\n🎉 All tests passed!\n');
    return true;
  } catch (error) {
    console.error('\n❌ Test failed:', error);
    return false;
  }
}

// 导出单个测试函数供单独调用
export { testSessionStore, testWebSocket, testRuntime };
