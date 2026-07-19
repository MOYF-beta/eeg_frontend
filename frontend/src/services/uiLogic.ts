/**
 * uiLogic — 从 Vue 组件中提取的纯 UI 逻辑，便于单元测试。
 */

/** 截断过长文本，防止 SVG <text> 溢出节点边界 */
export function truncateLabel(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  if (maxLen <= 1) return '…';
  return text.slice(0, maxLen - 1) + '…';
}

/** 设备分组面板的展开状态推进。
 *  openGroups === null 表示未初始化 → 默认全部展开；
 *  之后的空数组是用户主动全部折叠的合法状态，不得再强制展开。
 */
export function nextOpenGroups(current: string[] | null, allGroupKeys: string[]): string[] {
  if (current === null) return [...allGroupKeys];
  return current;
}

/** 格式化录制时长（如 8s / 1m05s） */
export function formatRecordingDuration(seconds: number): string {
  const secs = Math.max(0, Math.floor(seconds));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return m > 0 ? `${m}m${String(s).padStart(2, '0')}s` : `${s}s`;
}

/** 判断同步状态 chip 是否应显示（运行时隐藏 idle 的「编辑中」） */
export function shouldShowSyncChip(isRunning: boolean, syncStatus: 'idle' | 'saving' | 'ok' | 'error'): boolean {
  return !(isRunning && syncStatus === 'idle');
}
