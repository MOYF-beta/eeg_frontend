import { computed } from 'vue';
import { useDisplay } from 'vuetify';

/**
 * 侧边栏状态管理组合式函数 - 仅保留折叠态
 */
export function useSidebar() {
  const { mobile } = useDisplay();
  
  // 始终返回折叠态
  const sidebarState = computed(() => ({
    isCollapsed: true,
    isRail: true,
    width: 56,
    canHoverExpand: false
  }));
  
  // 内容区域边距
  const contentMargin = computed(() => 56);
  
  return {
    sidebarState,
    contentMargin,
    isMobile: mobile
  };
}