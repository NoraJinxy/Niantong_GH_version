// 地形图插值矩阵的 Web Worker：把「解方程 + 逐像素径向基(含 log) + 矩阵相乘」搬出主线程，
// 首次进页 / 切通道组不再卡那一下。入参=电极坐标；出参=inside + M（ArrayBuffer 转移，零拷贝）。
import { buildTopoKernel } from './topoKernel'

interface ReqMsg { sig: string; names: string[]; points: { x: number; y: number }[] }

const ctx: Worker = self as unknown as Worker
ctx.onmessage = (e: MessageEvent<ReqMsg>) => {
  const { sig, names, points } = e.data
  const k = buildTopoKernel(points)
  if (!k) {
    ctx.postMessage({ sig, failed: true })
    return
  }
  // names 原样回传供主线程对齐数值顺序；inside / M 的底层 buffer 转移，避免大数组拷贝
  ctx.postMessage(
    { sig, names, N: k.N, inside: k.inside.buffer, M: k.M.buffer },
    [k.inside.buffer as ArrayBuffer, k.M.buffer as ArrayBuffer],
  )
}
