// TimeCourseCanvas / HeatmapCanvas 共用的底层常量与纯函数，避免两处字面复制。
/** 设备像素比，上限 2（>2x 屏封顶；1x 屏不过采样）。 */
export const PX_RATIO = Math.min(window.devicePixelRatio || 1, 2)

/** 数值夹取到 [lo, hi]。 */
export function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v
}
