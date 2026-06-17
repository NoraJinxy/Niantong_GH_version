// 分面引擎（观察页画布共用）：叠加维度(seg/chan)→ 行/列因素 → 子图 cells + 共享轴布局。
// 时域/PSD/TFR 共用同一套「选中维度格内叠加、其余维度拆成子图(行/列)」的布局逻辑。
// 数据访问(读各 (seg,chan) 的 x/y/颜色)与布局无关 → 通过 buildCell 回调注入，保持本引擎域无关。
// 移植自 WaveformDetailPage 的 cells/facetStyle/legendCellIndex/denseAxes/gridCols/cellHide* 逻辑。
import { computed, type ComputedRef, type Ref } from 'vue'

type Factor = 'seg' | 'chan' | 'none'

/** buildCell 收到的「这一格画什么」上下文。 */
export interface FacetCellInput {
  /** 本格涉及的段（被网格钉死则 1 个，否则全部所选段）。 */
  segs: number[]
  /** 本格涉及的通道（被网格钉死则 1 个，否则全部所选通道）。 */
  chans: string[]
  multiSeg: boolean
  multiChan: boolean
  /** 段是否被摆到了行/列（决定叠加色按段还是按通道）。 */
  segIsGrid: boolean
}

export interface FacetCell {
  key: string
  title: string
  /** uPlot AlignedData：[x[], ...每条曲线 y[]]。 */
  data: number[][]
  series: { name: string; color: string }[]
  /** 本格涉及的段索引（seg 为 grid 因素时为 1 个，否则为全部所选段）。 */
  segs: number[]
}

export interface FacetGrid {
  effectiveOverlay: ComputedRef<'seg' | 'chan' | 'none'>
  facetDims: ComputedRef<Factor[]>
  rowFactor: ComputedRef<Factor>
  colFactor: ComputedRef<Factor>
  cells: ComputedRef<FacetCell[]>
  facetStyle: ComputedRef<Record<string, string>>
  legendCellIndex: ComputedRef<number>
  denseAxes: ComputedRef<boolean>
  gridCols: ComputedRef<number>
  cellHideX: (ci: number) => boolean
  cellHideY: (ci: number) => boolean
}

export function useFacetGrid(opts: {
  /** 已排序的所选段索引。 */
  segs: () => number[]
  /** 有序的所选通道名。 */
  chans: () => string[]
  /** 段总数（决定叠加维度是否退化到通道）。 */
  segCount: () => number
  /** 叠加维度（页面持有、可切换）。'none' = 两个维度均拆为子图（矩阵布局）。 */
  overlayDim: Ref<'seg' | 'chan' | 'none'>
  /** 段标签（子图标题用）。 */
  segLabel: (seg: number) => string
  /** 注入数据：返回本格的 AlignedData + series 配置（含颜色）。 */
  buildCell: (input: FacetCellInput) => { data: number[][]; series: { name: string; color: string }[] }
}): FacetGrid {
  // seg 只 1 个值时叠加维度强制落到通道（否则没东西可叠）
  const effectiveOverlay = computed<'seg' | 'chan' | 'none'>(() =>
    opts.overlayDim.value === 'seg' && opts.segCount() <= 1 ? 'chan' : opts.overlayDim.value,
  )
  // 当前可分面的维度（值>1、且不是叠加维度）：1 个→画廊；2 个→行×列矩阵；0 个→单格
  const facetDims = computed<Factor[]>(() => {
    const ov = effectiveOverlay.value
    const dims: Factor[] = []
    if (opts.segCount() > 1 && ov !== 'seg') dims.push('seg')
    if (opts.chans().length > 1 && ov !== 'chan') dims.push('chan')
    return dims
  })
  const rowFactor = computed<Factor>(() => (facetDims.value.length >= 2 ? facetDims.value[0] : 'none'))
  const colFactor = computed<Factor>(() => {
    const d = facetDims.value
    return d.length >= 2 ? d[1] : d.length === 1 ? d[0] : 'none'
  })

  const cells = computed<FacetCell[]>(() => {
    const chans = opts.chans()
    const segs = opts.segs()
    if (!chans.length || !segs.length) return []

    const rf = rowFactor.value
    const cf = colFactor.value
    const segIsGrid = rf === 'seg' || cf === 'seg'
    const rowVals: (number | string | null)[] = rf === 'seg' ? segs : rf === 'chan' ? chans : [null]
    const colVals: (number | string | null)[] = cf === 'seg' ? segs : cf === 'chan' ? chans : [null]

    const out: FacetCell[] = []
    for (const rv of rowVals) {
      for (const cv of colVals) {
        // 解析该格被网格钉死的 seg / channel
        const pinnedSeg = rf === 'seg' ? (rv as number) : cf === 'seg' ? (cv as number) : undefined
        const pinnedChan = rf === 'chan' ? (rv as string) : cf === 'chan' ? (cv as string) : undefined
        const cellSegs: number[] = pinnedSeg != null ? [pinnedSeg] : segs
        const cellChans: string[] = pinnedChan != null ? [pinnedChan] : chans

        const { data, series } = opts.buildCell({
          segs: cellSegs,
          chans: cellChans,
          multiSeg: cellSegs.length > 1,
          multiChan: cellChans.length > 1,
          segIsGrid,
        })

        const titleParts: string[] = []
        if (rf !== 'none') titleParts.push(rf === 'seg' ? opts.segLabel(rv as number) : String(rv))
        if (cf !== 'none') titleParts.push(cf === 'seg' ? opts.segLabel(cv as number) : String(cv))
        // key 带上当前选中段签名：改选段时强制重建子图，规避复用组件不刷新致空图
        out.push({
          key: `r:${String(rv)}|c:${String(cv)}|s:${segs.join(',')}`,
          title: titleParts.join(' · '),
          data,
          series,
          segs: cellSegs,
        })
      }
    }
    return out
  })

  // facet 网格列模板：两个分面维度→严格矩阵(列数=列因素值个数)；单/零分面维度→画廊式自适应换行
  const facetStyle = computed<Record<string, string>>(() => {
    const rf = rowFactor.value
    const cf = colFactor.value
    if (rf !== 'none' && cf !== 'none') {
      const n = (cf === 'seg' ? opts.segs().length : opts.chans().length) || 1
      return { gridTemplateColumns: `repeat(${n}, minmax(220px, 1fr))` }
    }
    return { gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }
  })

  // 图例去重：矩阵→右上角格；画廊/单因素→第一格
  const legendCellIndex = computed(() => {
    if (rowFactor.value !== 'none' && colFactor.value !== 'none') {
      const cols = (colFactor.value === 'seg' ? opts.segs().length : opts.chans().length) || 1
      return cols - 1
    }
    return 0
  })

  const denseAxes = computed(() => cells.value.length > 1)

  // 共享 facet 轴（仅严格矩阵、列数已知）：y 刻度只画最左列、x 刻度只画最底行
  const gridCols = computed(() => {
    if (rowFactor.value === 'none' || colFactor.value === 'none') return 0
    return (colFactor.value === 'seg' ? opts.segs().length : opts.chans().length) || 1
  })
  function cellHideY(ci: number): boolean {
    const cols = gridCols.value
    return cols > 0 && ci % cols !== 0
  }
  function cellHideX(ci: number): boolean {
    const cols = gridCols.value
    if (cols <= 0) return false
    const lastRow = Math.floor((cells.value.length - 1) / cols)
    return Math.floor(ci / cols) !== lastRow
  }

  return {
    effectiveOverlay,
    facetDims,
    rowFactor,
    colFactor,
    cells,
    facetStyle,
    legendCellIndex,
    denseAxes,
    gridCols,
    cellHideX,
    cellHideY,
  }
}
