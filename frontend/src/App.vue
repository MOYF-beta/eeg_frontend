<template>
  <v-app>
    <v-app-bar color="primary" prominent>
      <v-app-bar-title>EEG 脑电系统</v-app-bar-title>
      <v-spacer></v-spacer>
      <v-btn
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        :active="$route.path === item.path"
        variant="text"
        class="mx-1"
      >
        {{ item.title }}
      </v-btn>
    </v-app-bar>
    <v-main>
      <router-view />
    </v-main>
  </v-app>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';

const $route = useRoute();

const navItems = [
  { title: '设备', path: '/devices' },
  { title: '示波器', path: '/oscilloscope' },
  { title: '计算图', path: '/cpgraph' },
  { title: '测试', path: '/test' },
];
</script>
