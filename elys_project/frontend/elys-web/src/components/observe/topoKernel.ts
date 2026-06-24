// 地形图插值核（薄板样条 thin-plate spline）——纯计算、无 DOM，供 Web Worker 与主线程兜底共用。
// 电极位置在游标移动中不变、变的只有「每个电极的数值」，而样条曲面是数值的**线性函数**，
// 所以把「解方程 + 逐像素径向基（含 Math.log）+ 矩阵相乘」全压到**每个 montage 只做一次**，
// 得到常量插值矩阵 M（圈内像素 × 通道）；之后每帧只做 surface = M·v。这里只算 M（位置相关），不碰数值/配色/画布。
//
// 推导：样条系数 [w;a] = L⁻¹·[v;0;0;0]；像素 p 的曲面值 = b(p)·[w;a] = (b(p)·L⁻¹)[:N] · v ⇒ M = B·L⁻¹[:, :N]。

export const TOPO_RES = 96 // 离屏插值网格分辨率（RES×RES）

export interface TopoKernel {
  inside: Int32Array // 头罩圆内像素的扁平索引（py*RES+px）
  M: Float32Array // 形状 [inside.length × N] 行主序：像素曲面值对各通道数值的线性权重
  N: number // 通道数
}

// 薄板样条径向基 φ(r)=r²·ln r（入参为平方距离 r²），φ(0)=0
function tpsPhi(r2: number): number {
  return r2 <= 1e-12 ? 0 : 0.5 * r2 * Math.log(r2)
}

// 矩阵求逆（高斯-约当 + 部分主元，增广单位阵）；奇异（如电极共线）返回 null。n 小（≤几十），O(n³) 足够。
function invertMatrix(A: number[][]): number[][] | null {
  const n = A.length
  const M = A.map((row, i) => {
    const r = row.slice()
    for (let j = 0; j < n; j++) r.push(i === j ? 1 : 0)
    return r
  })
  for (let col = 0; col < n; col++) {
    let piv = col
    for (let r = col + 1; r < n; r++) if (Math.abs(M[r][col]) > Math.abs(M[piv][col])) piv = r
    if (Math.abs(M[piv][col]) < 1e-12) return null
    if (piv !== col) { const t = M[piv]; M[piv] = M[col]; M[col] = t }
    const pv = M[col][col]
    for (let j = col; j < 2 * n; j++) M[col][j] /= pv
    for (let r = 0; r < n; r++) {
      if (r === col) continue
      const f = M[r][col]
      if (f === 0) continue
      for (let j = col; j < 2 * n; j++) M[r][j] -= f * M[col][j]
    }
  }
  return M.map((row) => row.slice(n))
}

// 预算插值矩阵 M = B·L⁻¹[:, :N]。入参只需电极 2D 坐标（数值无关）。退化 montage 返回 null。
export function buildTopoKernel(points: { x: number; y: number }[]): TopoKernel | null {
  const N = points.length
  if (N < 3) return null
  const RES = TOPO_RES
  const m = N + 3
  // L = [[K, P],[Pᵀ, 0]]，K[i][j]=φ(|pi-pj|²)，P[i]=[1,xi,yi]
  const L: number[][] = Array.from({ length: m }, () => new Array(m).fill(0))
  for (let i = 0; i < N; i++) {
    for (let j = 0; j < N; j++) {
      const dx = points[i].x - points[j].x
      const dy = points[i].y - points[j].y
      L[i][j] = tpsPhi(dx * dx + dy * dy)
    }
    L[i][N] = 1; L[i][N + 1] = points[i].x; L[i][N + 2] = points[i].y
    L[N][i] = 1; L[N + 1][i] = points[i].x; L[N + 2][i] = points[i].y
  }
  const D = invertMatrix(L) // L⁻¹
  if (!D) return null
  // 圈内像素索引
  const insideArr: number[] = []
  for (let py = 0; py < RES; py++) {
    for (let px = 0; px < RES; px++) {
      const sx = -1 + ((px + 0.5) / RES) * 2
      const sy = -1 + ((py + 0.5) / RES) * 2
      if (sx * sx + sy * sy <= 1) insideArr.push(py * RES + px)
    }
  }
  const P = insideArr.length
  const M = new Float32Array(P * N)
  const b = new Float64Array(m)
  for (let p = 0; p < P; p++) {
    const idx = insideArr[p]
    const px = idx % RES
    const py = (idx / RES) | 0
    const sx = -1 + ((px + 0.5) / RES) * 2
    const sy = -1 + ((py + 0.5) / RES) * 2
    // SVG→数据坐标（数据 y 向上，故 dataY=-sy，与电极点 cy=-p.y 一致）
    const dataX = sx
    const dataY = -sy
    for (let k = 0; k < N; k++) {
      const ddx = dataX - points[k].x
      const ddy = dataY - points[k].y
      b[k] = tpsPhi(ddx * ddx + ddy * ddy)
    }
    b[N] = 1; b[N + 1] = dataX; b[N + 2] = dataY
    const rowBase = p * N
    for (let j = 0; j < N; j++) {
      let s = 0
      for (let k = 0; k < m; k++) s += b[k] * D[k][j]
      M[rowBase + j] = s
    }
  }
  return { inside: Int32Array.from(insideArr), M, N }
}
