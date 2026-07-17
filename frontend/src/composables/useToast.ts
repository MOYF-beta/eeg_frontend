/**
 * 全局 Toast 通知系统
 *
 * 替换项目中原生的 alert/confirm 调用。
 * 使用方式：
 *   import { useToast } from '../composables/useToast';
 *   const toast = useToast();
 *   toast.show('操作成功', 'success');
 *   toast.show('出错了', 'error');
 *   toast.show('提示信息', 'info');
 */

import { ref, reactive } from 'vue';

export interface ToastMessage {
  id: number;
  text: string;
  type: 'success' | 'error' | 'info' | 'warning';
  timeout: number;
}

const toasts = ref<ToastMessage[]>([]);
let nextId = 0;

function show(text: string, type: ToastMessage['type'] = 'info', timeout: number = 3000) {
  const id = nextId++;
  toasts.value.push({ id, text, type, timeout });
  if (timeout > 0) {
    setTimeout(() => {
      dismiss(id);
    }, timeout);
  }
  return id;
}

function dismiss(id: number) {
  const idx = toasts.value.findIndex((t) => t.id === id);
  if (idx !== -1) {
    toasts.value.splice(idx, 1);
  }
}

export function useToast() {
  return { toasts, show, dismiss };
}
