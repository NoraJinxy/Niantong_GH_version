<template>
  <div>
    <header class="topbar">
      <RouterLink to="/" class="topbar__brand" title="返回首页">
        <div class="logo">析</div>
        <div class="topbar__brand-text">念析 <small>ELYS</small></div>
      </RouterLink>

      <nav class="topbar__nav">
        <RouterLink
          v-for="item in topNavItems"
          :key="item.key"
          :to="item.to"
          :class="{ 'is-active': item.key === activeTopKey, 'is-preview': isWorkbenchNavPreview(item) }"
          :title="isWorkbenchNavPreview(item) ? `${item.label}：预览模块，尚未接入真实数据集和运行记录数据` : item.label"
        >
          <AppIcon :name="item.icon" :size="16" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="topbar__right">
        <button class="icon-btn" type="button" title="搜索">
          <AppIcon name="search" :size="16" />
        </button>
        <RouterLink class="icon-btn icon-btn--preview" to="/admin" title="设置：预览模块，尚未接入真实数据集和运行记录数据">
          <AppIcon name="settings" :size="16" />
        </RouterLink>
        <div class="user-chip" :title="`${user?.full_name || user?.username || 'PI'} · ${roleText}`">
          <div class="avatar">{{ userInitial }}</div>
          <span>{{ user?.full_name || user?.username || 'PI' }}</span>
        </div>
        <button v-if="!showSidebar" class="icon-btn" type="button" title="退出登录" @click="handleLogout">
          <AppIcon name="logout" :size="16" />
        </button>
      </div>
    </header>

    <div class="app" :class="{ 'app--immersive': !showSidebar }">
      <aside v-if="showSidebar" class="sidebar workbench-sidebar">
        <template v-for="group in sideNavGroups" :key="group.title">
          <div class="sidebar__title">{{ group.title }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.key"
            class="nav-item"
            :class="{ 'is-active': item.key === activeKey, 'is-preview': isWorkbenchNavPreview(item) }"
            :to="item.to"
            :title="isWorkbenchNavPreview(item) ? `${item.label}：预览模块，尚未接入真实数据集和运行记录数据` : item.label"
          >
            <AppIcon :name="item.icon" :size="17" />
            <span>{{ item.label }}</span>
            <span v-if="isWorkbenchNavPreview(item)" class="nav-item__status">预览</span>
          </RouterLink>
        </template>

        <div style="flex: 1"></div>
        <button class="nav-item" type="button" @click="handleLogout">
          <AppIcon name="logout" :size="17" />
          <span>退出登录</span>
        </button>
      </aside>

      <main class="page">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import { isWorkbenchNavPreview, sideNavGroups, topNavItems } from '@/data/workbenchPages'
import AppIcon from '@/components/AppIcon.vue'

const props = defineProps<{
  activeKey: string
  activeTopKey?: string
  showSidebar?: boolean
}>()

const auth = useAuthStore()
const { user } = storeToRefs(auth)

const activeTopKey = computed(() => props.activeTopKey || props.activeKey)
const showSidebar = computed(() => props.showSidebar !== false)
const roleText = computed(() => {
  const roles = user.value?.roles || []
  return roles.length ? roles.join(' / ') : 'pi'
})
const userInitial = computed(() => {
  const name = user.value?.full_name || user.value?.username || 'E'
  return name.slice(0, 1).toUpperCase()
})

function handleLogout() {
  auth.logout()
}
</script>
