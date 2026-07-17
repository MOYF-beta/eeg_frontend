import { computed } from 'vue';
import { useTheme } from 'vuetify';

const STORAGE_KEY = 'eeg-theme';

/**
 * 全局亮/暗主题切换。
 * - 首次访问跟随系统 prefers-color-scheme
 * - 手动切换后持久化到 localStorage
 */
export function useAppTheme() {
  const theme = useTheme();

  const isDark = computed(() => theme.global.current.value.dark);

  function initTheme() {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'dark' || saved === 'light') {
      theme.change(saved);
    } else if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
      theme.change('dark');
    }
  }

  function toggleTheme() {
    const next = isDark.value ? 'light' : 'dark';
    theme.change(next);
    localStorage.setItem(STORAGE_KEY, next);
  }

  return { isDark, initTheme, toggleTheme };
}
