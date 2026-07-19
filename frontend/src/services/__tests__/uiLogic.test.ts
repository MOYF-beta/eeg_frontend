// UI 纯逻辑单元测试（覆盖此前无测试的 UI 行为回归点）
import { describe, it, expect } from 'vitest';
import {
  truncateLabel,
  nextOpenGroups,
  formatRecordingDuration,
  shouldShowSyncChip,
} from '../uiLogic';

describe('truncateLabel（计算图节点文本防溢出）', () => {
  it('短文本原样返回', () => {
    expect(truncateLabel('滤波器', 20)).toBe('滤波器');
    expect(truncateLabel('', 20)).toBe('');
  });

  it('超长文本截断并加省略号', () => {
    const long = 'Alpha 波模拟器 (simulated:sim_alpha)';
    const out = truncateLabel(long, 20);
    expect(out.length).toBe(20);
    expect(out.endsWith('…')).toBe(true);
  });

  it('边界长度恰好等于 maxLen 时不截断', () => {
    expect(truncateLabel('12345', 5)).toBe('12345');
    expect(truncateLabel('123456', 5)).toBe('1234…');
  });

  it('maxLen 极小时保留 1 个字符加省略号', () => {
    expect(truncateLabel('abc', 1)).toBe('…');
    expect(truncateLabel('abc', 2)).toBe('a…');
  });
});

describe('nextOpenGroups（设备分组折叠状态）', () => {
  const keys = ['simulated', 'ch340'];

  it('未初始化（null）时默认全部展开', () => {
    expect(nextOpenGroups(null, keys)).toEqual(['simulated', 'ch340']);
  });

  it('用户全部折叠后保持折叠（不再被强制展开）', () => {
    expect(nextOpenGroups([], keys)).toEqual([]);
  });

  it('保留用户部分展开的选择', () => {
    expect(nextOpenGroups(['ch340'], keys)).toEqual(['ch340']);
  });
});

describe('formatRecordingDuration（状态栏录制时长）', () => {
  it('秒级时长', () => {
    expect(formatRecordingDuration(0)).toBe('0s');
    expect(formatRecordingDuration(8.9)).toBe('8s');
    expect(formatRecordingDuration(59)).toBe('59s');
  });

  it('分钟级时长补零', () => {
    expect(formatRecordingDuration(60)).toBe('1m00s');
    expect(formatRecordingDuration(65)).toBe('1m05s');
    expect(formatRecordingDuration(600)).toBe('10m00s');
  });

  it('负值按 0 处理', () => {
    expect(formatRecordingDuration(-5)).toBe('0s');
  });
});

describe('shouldShowSyncChip（运行时隐藏「编辑中」）', () => {
  it('未运行时各状态均显示', () => {
    expect(shouldShowSyncChip(false, 'idle')).toBe(true);
    expect(shouldShowSyncChip(false, 'saving')).toBe(true);
    expect(shouldShowSyncChip(false, 'ok')).toBe(true);
    expect(shouldShowSyncChip(false, 'error')).toBe(true);
  });

  it('运行时仅隐藏 idle，其余状态仍显示', () => {
    expect(shouldShowSyncChip(true, 'idle')).toBe(false);
    expect(shouldShowSyncChip(true, 'saving')).toBe(true);
    expect(shouldShowSyncChip(true, 'ok')).toBe(true);
    expect(shouldShowSyncChip(true, 'error')).toBe(true);
  });
});
