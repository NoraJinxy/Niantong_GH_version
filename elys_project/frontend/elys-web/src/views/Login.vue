<template>
  <main class="auth-stage">
    <RouterLink class="auth-back" to="/">
      <svg class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M19 12H5M12 19l-7-7 7-7" />
      </svg>
      返回首页
    </RouterLink>

    <div class="auth-card">
      <RouterLink class="auth-brand auth-brand--link" to="/" title="返回首页">
        <div class="logo"><svg viewBox="0 0 32 32" fill="none" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19 H8.5 C9.6 19 10 21 11.2 21 C12.6 21 13 8 15.8 8 C18.6 8 19 19 20.4 19 H28"/></svg></div>
        <h1>念析 <small>ELYS</small></h1>
        <small class="tagline">念隐于微，析显于明</small>
      </RouterLink>

      <div v-if="error" class="alert alert--danger">
        <svg class="alert__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h0" />
        </svg>
        <div>
          <div class="alert__title">登录失败</div>
          <div class="alert__body">{{ error }}</div>
        </div>
      </div>

      <form @submit.prevent="handleLogin">
        <div class="field">
          <label class="field__label">用户名</label>
          <input
            v-model="form.username"
            type="text"
            class="input"
            :class="{ 'is-error': !!error }"
            placeholder="admin / user1 / user2"
            autocomplete="username"
            required
          />
        </div>

        <div class="field">
          <label class="field__label">密码</label>
          <div class="password-wrap">
            <input
              v-model="form.password"
              :type="showPwd ? 'text' : 'password'"
              class="input"
              :class="{ 'is-error': !!error }"
              placeholder="请输入密码"
              autocomplete="current-password"
              required
            />
            <button type="button" class="eye" :title="showPwd ? '隐藏' : '显示'" @click="showPwd = !showPwd">
              <svg v-if="!showPwd" class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg v-else class="ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
                <path d="M2 12s3.5-7 10-7c2.2 0 4.1.7 5.7 1.6M22 12s-3.5 7-10 7c-2.2 0-4.1-.7-5.7-1.6" />
                <path d="M3 3l18 18" />
              </svg>
            </button>
          </div>
        </div>

        <div class="helper-row mb-4">
          <label class="checkbox">
            <input type="checkbox" v-model="remember" />
            <span>记住此设备</span>
          </label>
        </div>

        <button
          type="submit"
          class="btn btn--primary btn--block btn--lg"
          :disabled="loading"
        >
          <span v-if="loading" class="spinner"></span>
          {{ loading ? '登录中...' : '登 录' }}
        </button>
      </form>

      <div class="alert alert--info mt-4">
        <svg class="alert__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h0" />
        </svg>
        <div>
          <div class="alert__title">测试账号</div>
          <div class="alert__body">
            测试账号由本地私有 seed 或部署环境提供
          </div>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { loading, error } = storeToRefs(auth)

const form = reactive({ username: '', password: '' })
const showPwd = ref(false)
const remember = ref(true)

async function handleLogin() {
  try {
    await auth.login(form)
  } catch {
    // error is set by store
  }
}
</script>
