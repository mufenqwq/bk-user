<template>
  <bk-tab
    class="tab-wrapper"
    v-model:active="active"
    type="unborder-card"
  >
    <bk-tab-panel
      v-for="item in panels"
      :key="item.name"
      :name="item.name"
      :label="item.label"
    >
      <component :is="item.component" :active="active"></component>
    </bk-tab-panel>
  </bk-tab>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref  } from 'vue';

import { t } from '@/language/index';
import router from '@/router';
import { useMainViewStore } from '@/store';

const MyShare = defineAsyncComponent(() => import('./my-share/index.vue'));
const OtherShare = defineAsyncComponent(() => import('./other-share/index.vue'));

const store = useMainViewStore();
store.customBreadcrumbs = false;

const panels = [
  { name: 'local', label: t('我分享的'), component: MyShare },
  { name: 'other', label: t('其他租户分享的'), component: OtherShare },
];
const active = ref(router.currentRoute.value.query.tab ?? 'local');
</script>

<style lang="less" scoped>
.tab-wrapper {
  // 顶部固定开销 = 面包屑 + tab 头（引用 --header-height，iframe 嵌入时自动归零）
  --header-total: calc(var(--header-height) + var(--breadcrumbs-height) + var(--tab-height));

  :deep(.bk-tab-header) {
    padding-left: 24px;
    font-size: 14px;
    line-height: var(--tab-height) !important;
    background: #fff;
    border-bottom: none;
    box-shadow: 0 3px 4px 0 rgb(0 0 0 / 4%);
  }

  :deep(.bk-tab-content) {
    padding: 0;
  }
}
</style>
