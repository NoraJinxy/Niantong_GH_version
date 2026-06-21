<template>
  <Modal @close="$emit('close')">
    <div class="hk-card" role="dialog" aria-label="键盘快捷键">
      <div class="hk-hd">
        <strong>键盘快捷键</strong>
        <span class="hk-hint">按 <kbd>?</kbd> 或 <kbd>Esc</kbd> 关闭</span>
      </div>
      <div class="hk-body">
        <section v-for="s in groups" :key="s.group" class="hk-sec">
          <div class="hk-sec-ttl">{{ s.title }}</div>
          <div v-for="d in s.items" :key="d.key" class="hk-row">
            <span class="hk-keys">
              <kbd v-for="(t, i) in fmtKey(d.key)" :key="i">{{ t }}</kbd>
            </span>
            <span class="hk-lbl">{{ d.label }}</span>
          </div>
        </section>
      </div>
    </div>
  </Modal>
</template>

<script setup lang="ts">
// 快捷键速查卡：由 useObserveHotkeys 的 helpGroups 驱动，按当前视图可用键分组展示。
import Modal from '@/components/common/Modal.vue'
import type { HotkeyDef, HotkeyGroup } from '@/composables/observe/useObserveHotkeys'

defineProps<{ groups: { group: HotkeyGroup; title: string; items: HotkeyDef[] }[] }>()
defineEmits<{ (e: 'close'): void }>()

const GLYPH: Record<string, string> = {
  ArrowLeft: '←', ArrowRight: '→', ArrowUp: '↑', ArrowDown: '↓',
  Enter: '↵', Escape: 'Esc', ' ': 'Space', Ctrl: 'Ctrl', Shift: 'Shift', Alt: 'Alt',
}
function fmtKey(k: string): string[] {
  return k.split('+').map((t) => GLYPH[t] ?? (t.length === 1 ? t.toUpperCase() : t))
}
</script>

<style scoped>
.hk-card { width: min(560px, 88vw); max-height: 80vh; display: flex; flex-direction: column; background: var(--c-surface); border: 1px solid var(--c-border); border-radius: var(--r-md); box-shadow: var(--shadow-lg); overflow: hidden; }
.hk-hd { flex-shrink: 0; display: flex; align-items: baseline; justify-content: space-between; gap: 12px; padding: 13px 16px; border-bottom: 1px solid var(--c-border); }
.hk-hd strong { font-size: 14px; color: var(--c-text); }
.hk-hint { font-size: 12px; color: var(--c-text-3); }
.hk-body { overflow-y: auto; padding: 12px 16px; display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 4px 24px; align-content: start; }
.hk-sec { break-inside: avoid; margin-bottom: 8px; }
.hk-sec-ttl { font-size: 11px; font-weight: 600; color: var(--c-text-3); text-transform: uppercase; letter-spacing: .04em; margin: 6px 0 4px; }
.hk-row { display: flex; align-items: center; gap: 8px; padding: 3px 0; font-size: 13px; color: var(--c-text-2); }
.hk-keys { flex-shrink: 0; display: inline-flex; gap: 3px; min-width: 76px; }
.hk-lbl { min-width: 0; }
.hk-row kbd { font-family: var(--ff-mono, monospace); font-size: 11px; line-height: 1.5; min-width: 18px; text-align: center; padding: 1px 5px; background: var(--c-bg-soft); border: 1px solid var(--c-border); border-bottom-width: 2px; border-radius: 5px; color: var(--c-text); }
</style>
