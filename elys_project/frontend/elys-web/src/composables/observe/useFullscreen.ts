import { ref, onMounted, onUnmounted, type Ref } from 'vue'

/** 三页观察页共用的全屏开关：内部注册 fullscreenchange 监听，调用方无需手动 add/removeEventListener。 */
export function useFullscreen(pageRef: Ref<HTMLElement | null>) {
  const isFullscreen = ref(false)

  function toggleFullscreen() {
    const el = pageRef.value
    if (!el) return
    if (document.fullscreenElement) void document.exitFullscreen()
    else void el.requestFullscreen()
  }

  function onFsChange() {
    isFullscreen.value = !!document.fullscreenElement
  }

  onMounted(() => document.addEventListener('fullscreenchange', onFsChange))
  onUnmounted(() => document.removeEventListener('fullscreenchange', onFsChange))

  return { isFullscreen, toggleFullscreen }
}
