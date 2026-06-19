<template>
  <router-view />
  <!-- 调试期版本角标：右下角浅灰小字，显示构建时刻（+ 本地 git hash）。部署后一眼确认「跑的是不是最新代码」；调试期结束可删本块。 -->
  <div class="build-stamp">build {{ buildLabel }}</div>
</template>

<script setup lang="ts">
const t = new Date(__BUILD_TIME__)
const pad = (n: number) => String(n).padStart(2, '0')
const time = `${pad(t.getMonth() + 1)}-${pad(t.getDate())} ${pad(t.getHours())}:${pad(t.getMinutes())}`
const buildLabel = __BUILD_HASH__ === 'nogit' ? time : `${time} · ${__BUILD_HASH__}`
</script>

<style scoped>
.build-stamp {
  position: fixed;
  right: 6px;
  bottom: 4px;
  z-index: 99999;
  font-size: 10px;
  line-height: 1;
  color: rgba(120, 133, 154, 0.5);
  font-family: ui-monospace, SFMono-Regular, monospace;
  pointer-events: none;
  user-select: none;
}
</style>
