import { ref, computed, watch } from 'vue';
import { useDisplay } from 'vuetify';

/**
 * 侧边栏状态管理组合式函数
 */
export function useSidebar() {
  const { mobile, width } = useDisplay();
  
  // 侧边栏状态
  const isCollapsed = ref(false);
  const isHovered = ref(false);
  
  // 响应式侧边栏状态
  const sidebarState = computed(() => {
    // 在移动设备上默认折叠
    if (mobile.value) {
      return {
        isCollapsed: true,
        isRail: true,
        width: 56,
        canHoverExpand: false
      };
    }
    
    // 在桌面设备上根据状态计算
    if (isCollapsed.value) {
      return {
        isCollapsed: true,
        isRail: true,
        width: 56, // 固定宽度，不随悬停变化
        canHoverExpand: false // 禁用悬停展开
      };
    }
    
    return {
      isCollapsed: false,
      isRail: false,
      width: 256,
      canHoverExpand: false
    };
  });
  
  // 内容区域边距
  const contentMargin = computed(() => {
    const state = sidebarState.value;
    return state.isCollapsed && !state.isRail ? 256 : state.width;
  });
  
  // 切换侧边栏状态
  const toggleSidebar = () => {
    isCollapsed.value = !isCollapsed.value;
    isHovered.value = false;
  };
  
  // 展开侧边栏
  const expandSidebar = () => {
    isCollapsed.value = false;
    isHovered.value = false;
  };
  
  // 折叠侧边栏
  const collapseSidebar = () => {
    isCollapsed.value = true;
    isHovered.value = false;
  };
  
  // 鼠标悬停事件（已禁用悬停展开）
  const onMouseEnter = () => {
    // 悬停时不展开，保持当前状态
  };
  
  const onMouseLeave = () => {
    // 悬停时不展开，保持当前状态
  };
  
  // 监听屏幕宽度变化
  watch(width, (newWidth) => {
    // 在小屏幕上自动折叠侧边栏
    if (newWidth < 960) {
      isCollapsed.value = true;
    }
  }, { immediate: true });
  
  return {
    // 状态
    isCollapsed,
    isHovered,
    sidebarState,
    contentMargin,
    
    // 方法
    toggleSidebar,
    expandSidebar,
    collapseSidebar,
    onMouseEnter,
    onMouseLeave,
    
    // 响应式属性
    isMobile: mobile
  };
}