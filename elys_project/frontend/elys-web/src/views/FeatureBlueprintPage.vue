<template>
  <WorkbenchShell active-key="dashboard" active-top-key="dashboard">
    <template v-if="blueprint">
      <RouterLink class="bp-back" to="/dashboard">
        <AppIcon name="logout" :size="14" class="bp-back__arrow" />
        返回工作台
      </RouterLink>

      <div class="page__header bp-hero">
        <div class="bp-hero__copy">
          <span class="badge badge--primary">
            <span class="dot"></span>{{ blueprint.eyebrow }}
          </span>
          <div class="bp-hero__title-row">
            <div class="bp-hero__icon">
              <AppIcon :name="blueprint.icon" :size="24" />
            </div>
            <h1 class="page__title">{{ blueprint.title }}</h1>
          </div>
          <p class="page__subtitle bp-hero__summary">{{ blueprint.summary }}</p>
        </div>
        <div class="bp-hero__status">
          <span class="badge badge--outline">当前状态</span>
          <span class="badge" :class="statusBadgeClass">{{ statusLabel }}</span>
        </div>
      </div>

      <!-- 进度条：已实现 / 总条目 -->
      <div class="card bp-progress">
        <div class="bp-progress__head">
          <strong>实现进度</strong>
          <span>已落地 {{ blueprint.done.length }} / {{ totalItems }} 项 · {{ progressPercent }}%</span>
        </div>
        <div class="progress progress--lg progress--success">
          <div class="progress__bar" :style="{ width: `${progressPercent}%` }"></div>
        </div>
      </div>

      <!-- ① 这个功能要做什么 -->
      <section class="card bp-section">
        <div class="card__header">
          <div>
            <h3 class="card__title">这个功能要做什么</h3>
            <div class="card__sub">面向使用者的目标，而不是技术细节</div>
          </div>
        </div>
        <ul class="bp-intent">
          <li v-for="line in blueprint.intent" :key="line">
            <span class="bp-intent__dot"></span>
            <span>{{ line }}</span>
          </li>
        </ul>
      </section>

      <!-- ② 已实现 / ③ 待实现 两栏 -->
      <div class="grid grid-2 bp-cols">
        <section class="card bp-section">
          <div class="card__header">
            <div>
              <h3 class="card__title">已经实现</h3>
              <div class="card__sub">可依赖的底座能力</div>
            </div>
            <span class="badge badge--success">{{ blueprint.done.length }} 项</span>
          </div>
          <ul class="bp-list">
            <li v-for="item in blueprint.done" :key="item" class="bp-item bp-item--done">
              <span class="bp-mark bp-mark--done"><AppIcon name="check" :size="13" /></span>
              <span>{{ item }}</span>
            </li>
          </ul>
        </section>

        <section class="card bp-section">
          <div class="card__header">
            <div>
              <h3 class="card__title">还没实现</h3>
              <div class="card__sub">本功能本身的待办</div>
            </div>
            <span class="badge badge--outline">{{ blueprint.todo.length }} 项</span>
          </div>
          <ul class="bp-list">
            <li v-for="item in blueprint.todo" :key="item" class="bp-item bp-item--todo">
              <span class="bp-mark bp-mark--todo"></span>
              <span>{{ item }}</span>
            </li>
          </ul>
        </section>
      </div>

      <p class="bp-note">
        <AppIcon name="clock" :size="14" />
        这是一个「功能蓝图」占位页：功能尚未完成，先在这里讲清要做什么、已实现什么、还差什么。完成后，入口会自动替换为真实功能，本页随之退场。
      </p>
    </template>

    <!-- key 不存在或已上线时的兜底 -->
    <div v-else class="bp-empty">
      <div class="bp-empty__icon"><AppIcon name="search" :size="28" /></div>
      <strong>没有找到这个功能蓝图</strong>
      <p>蓝图标识「{{ routeKey }}」不存在，或对应功能已上线。</p>
      <RouterLink class="btn btn--primary btn--sm" to="/dashboard">返回工作台</RouterLink>
    </div>
  </WorkbenchShell>
</template>

<script setup lang="ts">
import { computed, watchEffect } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppIcon from '@/components/AppIcon.vue'
import WorkbenchShell from '@/components/WorkbenchShell.vue'
import { getFeatureBlueprint, type FeatureBlueprintStatus } from '@/data/featureBlueprints'

const route = useRoute()
const router = useRouter()

const routeKey = computed(() => String(route.params.blueprintKey || ''))
const blueprint = computed(() => getFeatureBlueprint(routeKey.value))

const totalItems = computed(() =>
  blueprint.value ? blueprint.value.done.length + blueprint.value.todo.length : 0,
)
const progressPercent = computed(() => {
  if (!blueprint.value || totalItems.value === 0) return 0
  return Math.round((blueprint.value.done.length / totalItems.value) * 100)
})

const STATUS_LABEL: Record<FeatureBlueprintStatus, string> = {
  planned: '规划中',
  building: '开发中',
  live: '已上线',
}
const STATUS_BADGE: Record<FeatureBlueprintStatus, string> = {
  planned: 'badge--outline',
  building: 'badge--warning',
  live: 'badge--success',
}
const statusLabel = computed(() => (blueprint.value ? STATUS_LABEL[blueprint.value.status] : ''))
const statusBadgeClass = computed(() =>
  blueprint.value ? STATUS_BADGE[blueprint.value.status] : 'badge--outline',
)

// 无缝替换：若功能已上线且配了真实路由，直接转走——旧书签/旧链接也能落到真功能上。
watchEffect(() => {
  const bp = blueprint.value
  if (bp && bp.status === 'live' && bp.liveRoute) {
    router.replace(bp.liveRoute)
  }
})
</script>

<style scoped>
.bp-back {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: var(--s-3);
  color: var(--c-text-2);
  font-size: 13px;
  text-decoration: none;
}
.bp-back:hover { color: var(--c-primary); }
.bp-back__arrow { transform: rotate(180deg); }

.bp-hero {
  align-items: flex-start;
}
.bp-hero__copy {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
}
.bp-hero__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.bp-hero__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: var(--r-md);
  color: var(--c-primary);
  background: var(--c-primary-soft);
  flex-shrink: 0;
}
.bp-hero__summary {
  font-size: 14px;
  line-height: 1.6;
  max-width: 70ch;
}
.bp-hero__status {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.bp-progress {
  margin-bottom: var(--s-4);
}
.bp-progress__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-3);
  margin-bottom: 10px;
}
.bp-progress__head strong { font-size: 14px; }
.bp-progress__head span { color: var(--c-text-2); font-size: 13px; }

.bp-section { margin-bottom: var(--s-4); }

.bp-intent {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bp-intent li {
  display: flex;
  gap: 10px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--c-text);
}
.bp-intent__dot {
  flex-shrink: 0;
  width: 7px;
  height: 7px;
  margin-top: 8px;
  border-radius: 50%;
  background: var(--c-primary);
}

.bp-cols { margin-bottom: var(--s-4); }

.bp-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.bp-item {
  display: flex;
  gap: 10px;
  font-size: 13.5px;
  line-height: 1.55;
}
.bp-item--todo { color: var(--c-text-2); }
.bp-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  border-radius: 50%;
}
.bp-mark--done {
  color: var(--c-success);
  background: var(--c-success-soft);
}
.bp-mark--todo {
  width: 14px;
  height: 14px;
  margin: 4px 3px 0 3px;
  border: 1.8px dashed var(--c-border-2);
  background: transparent;
}

.bp-note {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: var(--s-3) var(--s-4);
  border: 1px dashed var(--c-border-2);
  border-radius: var(--r-md);
  background: var(--c-bg-soft);
  color: var(--c-text-2);
  font-size: 13px;
  line-height: 1.6;
}
.bp-note .ico { flex-shrink: 0; margin-top: 2px; }

.bp-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 64px 24px;
  text-align: center;
}
.bp-empty__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  color: var(--c-text-3);
  background: var(--c-bg-tint);
  margin-bottom: 4px;
}
.bp-empty strong { font-size: 16px; }
.bp-empty p { margin: 0 0 8px; color: var(--c-text-2); font-size: 13px; }
</style>
