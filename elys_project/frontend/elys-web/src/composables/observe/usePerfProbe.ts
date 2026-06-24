// 临时性能探针：各观察/审核页插，测「挂载 / 数据就绪 / 渲染」等里程碑（均为自 setup 起的绝对毫秒）。
// 用法：const probe = usePerfProbe('psd')；数据就绪处 probe.done('数据')；其后 probe.paint()；末尾 probe.log()。
// 模板放 <PerfBadge :perf="probe.perf" />。测完整套删除（本文件 + PerfBadge.vue + 各页 3~4 行）。
import { onMounted, reactive } from 'vue'

export function usePerfProbe(label: string) {
  const t0 = performance.now()
  const perf = reactive<Record<string, number>>({})
  /** 记一个里程碑：自组件 setup 起的绝对耗时(ms)。差值即各阶段成本。 */
  function done(name: string) {
    perf[name] = Math.round(performance.now() - t0)
  }
  /** 下一帧记「渲染」：数据 set 后调，捕获 Vue patch + 画布首绘那一拍。 */
  function paint(name = '渲染') {
    requestAnimationFrame(() => done(name))
  }
  /** 打到 console（带 label，便于区分页面）。 */
  function log() {
    console.log(`[perf ${label}]`, { ...perf })
  }
  onMounted(() => {
    perf['挂载'] = Math.round(performance.now() - t0)
  })
  return { perf, done, paint, log }
}
