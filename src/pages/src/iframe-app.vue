<script setup lang="ts">
import App from './app.vue';

// iframe 嵌入（subEnv）时使用的入口组件。
// 复用 App.vue 的完整业务逻辑（登录守卫、用户信息、多语言等），隐藏顶部导航，
// 仅渲染业务内容区（主系统门户自带导航，子系统不再展示自身顶栏）。
</script>

<template>
  <App hide-header />
</template>
