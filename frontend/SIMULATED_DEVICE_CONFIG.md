# 模拟设备配置功能说明

## 功能概述

前端添加了模拟设备配置功能，允许用户为模拟设备指定信号类型和噪声参数。支持以下功能：

### 信号类型
1. **正弦波** - 标准正弦波信号
2. **方波** - 可配置占空比的方波信号
3. **三角波** - 三角波信号
4. **脉冲** - 可配置宽度和占空比的脉冲信号
5. **多个正弦波叠加** - 多个不同频率、幅度和相位的正弦波叠加

### 噪声类型
1. **无噪声** - 纯净信号
2. **白噪声** - 全频段均匀分布的噪声
3. **粉红噪声** - 频率反比噪声（1/f噪声）
4. **布朗噪声** - 布朗运动噪声（1/f²噪声）
5. **高斯噪声** - 高斯分布噪声

## 使用方法

### 1. 添加模拟设备
1. 在设备列表页面点击"添加设备"按钮
2. 选择设备类型为"simulated"
3. 填写设备基本信息（名称、采样率、通道数）
4. 展开"模拟设备配置"面板
5. 配置每个通道的信号和噪声参数

### 2. 配置信号参数
每个通道可以独立配置：
- **信号类型**：选择信号波形
- **频率**：信号频率（Hz）
- **幅度**：信号幅度
- **相位**：信号相位（度）
- **占空比**：方波和脉冲的占空比（0-1）
- **脉冲宽度**：脉冲信号的宽度（秒）
- **正弦波分量**：多个正弦波叠加时，可添加多个分量

### 3. 配置噪声参数
每个通道可以独立配置：
- **噪声类型**：选择噪声类型
- **噪声幅度**：噪声的幅度
- **随机种子**：可选的随机种子（留空使用随机值）
- **截止频率**：粉红噪声和布朗噪声的截止频率（Hz）
- **标准差**：高斯噪声的标准差

### 4. 全局噪声配置
可以为整个设备配置全局噪声，会叠加到所有通道上。

### 5. 快速操作
- **应用到所有通道**：将第一个通道的配置复制到所有通道
- **重置所有通道**：将所有通道重置为默认配置

## 数据结构

### Device 接口扩展
```typescript
interface Device {
  id: string;
  name: string;
  status: 'online' | 'offline';
  sampleRate: number;
  channels: number;
  port?: string;
  type?: 'simulated' | 'physical';
  config?: SimulatedDeviceConfig; // 新增：模拟设备配置
}
```

### 模拟设备配置结构
```typescript
interface SimulatedDeviceConfig {
  channels: ChannelConfig[];
  globalNoise?: NoiseConfig;
}

interface ChannelConfig {
  index: number;
  signal: SignalConfig;
  noise?: NoiseConfig;
  enabled: boolean;
}

interface SignalConfig {
  type: 'sine' | 'square' | 'triangle' | 'pulse' | 'multi_sine';
  frequency: number;
  amplitude: number;
  phase?: number;
  dutyCycle?: number;
  pulseWidth?: number;
  sineComponents?: {
    frequency: number;
    amplitude: number;
    phase: number;
  }[];
}

interface NoiseConfig {
  type: 'none' | 'white' | 'pink' | 'brownian' | 'gaussian';
  amplitude: number;
  seed?: number;
  cutoffFrequency?: number;
}
```

## 组件说明

### 1. DeviceList.vue
- 主设备管理组件
- 集成了模拟设备配置对话框
- 根据设备类型显示/隐藏配置选项

### 2. SimulatedDeviceConfig.vue
- 模拟设备配置主组件
- 管理所有通道的配置
- 提供全局噪声配置
- 提供快速操作按钮

### 3. SignalConfigEditor.vue
- 信号配置编辑器
- 支持所有信号类型的参数配置
- 提供实时预览信息

### 4. NoiseConfigEditor.vue
- 噪声配置编辑器
- 支持所有噪声类型的参数配置
- 提供实时预览信息

## 默认值

### 信号默认值
- 类型：正弦波
- 频率：10 Hz
- 幅度：100
- 相位：0°

### 噪声默认值
- 类型：无噪声
- 幅度：0

## 注意事项

1. **通道数变化**：当修改通道数时，配置会自动调整
2. **配置保存**：配置会随设备信息一起保存到 sessionStore
3. **向后兼容**：现有设备不受影响，新增的 config 字段为可选
4. **类型安全**：所有配置都有完整的 TypeScript 类型定义
5. **用户体验**：使用 Vuetify 组件，保持与现有界面一致

## 扩展建议

1. **信号预览**：添加实时信号波形预览
2. **预设配置**：添加常用信号配置预设
3. **导入导出**：支持配置的导入导出功能
4. **批量编辑**：增强批量编辑功能
5. **高级噪声**：添加更多噪声类型和参数