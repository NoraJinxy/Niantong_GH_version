// 观察页三页共用：拦掉「滚轮落在已聚焦的数字输入框上偷偷增减其值」这一原生行为。
// 这些页面把滚轮训练成「缩放图表」（Ctrl+滚轮调幅/色阶），若光标恰好停在某个工具条数字框上
// 滚动，浏览器默认会改框里的数字（且 @change 会在失焦时把它应用出去）——与肌肉记忆相悖。
// 做法：在页根挂一个非 passive 的 wheel 委托监听，命中「鼠标正停在当前聚焦的 number 输入框上」才
// preventDefault 阻止改值——但**不再 blur 失焦**（否则点框后一碰滚轮就失焦、键盘编辑被打断；用户选「键盘为主」）。
// 因为拦截条件是「鼠标在聚焦框上」，想缩放图只要把鼠标移到图上滚即可（target≠框→不拦），无需失焦。
// 落在画布或非输入框上的滚轮一律不碰，画布自有其手势。
import { onMounted, onUnmounted, type Ref } from 'vue'

export function useNumberWheelGuard(root: Ref<HTMLElement | null>) {
  function onWheel(e: WheelEvent) {
    const el = e.target
    if (el instanceof HTMLInputElement && el.type === 'number' && el === document.activeElement) {
      e.preventDefault()
    }
  }
  onMounted(() => root.value?.addEventListener('wheel', onWheel, { passive: false }))
  onUnmounted(() => root.value?.removeEventListener('wheel', onWheel))
}
