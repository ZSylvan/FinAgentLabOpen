<template>
  <section class="evaluation-page" aria-labelledby="evaluation-title">
    <header>
      <p class="eyebrow">Evaluation</p>
      <h1 id="evaluation-title">历史回顾评估</h1>
      <p>查看已发布的 A 股历史回顾评估结果。</p>
    </header>

    <section v-if="authStore.isAdmin" aria-labelledby="management-title">
      <h2 id="management-title">Evaluation 管理</h2>
      <p>管理员可以在后续功能中创建、取消和发布评估。</p>
    </section>

    <section v-else aria-labelledby="viewer-title">
      <h2 id="viewer-title">只读访问</h2>
      <p>你可以查看管理员已发布的评估，管理操作仅对管理员开放。</p>
    </section>

    <section aria-labelledby="history-title">
      <h2 id="history-title">Evaluation History</h2>
      <p>当前还没有可显示的评估记录。</p>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

onMounted(async () => {
  try {
    await authStore.fetchUserInfo()
  } catch (error) {
    console.warn('刷新 Evaluation 访问身份失败:', error)
  }
})
</script>

<style scoped>
.evaluation-page {
  display: grid;
  gap: 24px;
}

.evaluation-page > header,
.evaluation-page > section {
  padding: 24px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  background: var(--el-bg-color);
}

.evaluation-page h1,
.evaluation-page h2,
.evaluation-page p {
  margin-top: 0;
}

.evaluation-page p:last-child {
  margin-bottom: 0;
  color: var(--el-text-color-secondary);
}

.eyebrow {
  margin-bottom: 8px;
  color: var(--el-color-primary) !important;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
</style>
