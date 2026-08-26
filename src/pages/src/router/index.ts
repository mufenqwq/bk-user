import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router';

import { connectToMain } from '@blueking/sub-saas';

import { routes } from './routes';

const router = createRouter({
  history: process.env.BK_DESIGN_PREVIEW === 'true'
    ? createWebHashHistory()
    : createWebHistory(window.SITE_URL),
  routes,
});

connectToMain(router);

export default router;
