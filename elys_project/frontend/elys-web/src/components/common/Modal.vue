<!-- 通用弹窗外壳：固定遮罩 + 居中 + 点遮罩/按 Esc 关闭（emit('close')）。
     卡片本体（.modal-card 等）由调用方放进默认插槽——本组件只负责「罩 + 居中 + 关闭手势」，
     所以各处现有弹窗几乎零改造即可接入，并统一补上此前缺失的 Esc 关闭。
     遮罩样式与各页原 .modal-backdrop 一致；卡片样式仍由调用方提供（插槽内容沿用父作用域）。 -->
<template>
  <div class="modal-backdrop" role="presentation" @click.self="emit('close')">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const emit = defineEmits<{ close: [] }>()

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}
onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgb(15 23 42 / 45%);
}
</style>
