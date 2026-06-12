<template>
  <div class="view-container">
    <slot />
  </div>
</template>

<script setup lang="ts">
// 这是一个通用的视图容器组件，确保所有视图都能充分利用主内容区域的空间
</script>

<style scoped>
.view-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: 100%;
  overflow: hidden;
}

/* 确保容器内的内容也能正确布局 */
.view-container > * {
  flex: 1;
  min-height: 0;
}
</style>