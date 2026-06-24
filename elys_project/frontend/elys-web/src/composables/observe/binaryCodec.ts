// 通用数值二进制容器 ELYSBIN1 解码（与后端 app/pipeline/binary_codec.py 对应）。
// 一个 decode 通吃各观察端点的二进制：meta(JSON) 描述业务字段 + arrays[{name,dtype,count}]，其后紧排各扁平浮点数组。
// 与时域专用的 EEGBIN01（plotCache.decodeBinary）并存——后者历史格式不动，新接入统一走本容器。

export interface ElysArrayDesc {
  name: string
  dtype: 'f4' | 'f8'
  count: number
}
export interface ElysBin {
  meta: Record<string, unknown> & { arrays?: ElysArrayDesc[] }
  arrays: Record<string, Float32Array | Float64Array>
}

const MAGIC = 'ELYSBIN1'

/** 是否 ELYSBIN1 容器（前 8 字节 magic）。用于二进制/JSON 回退判别。 */
export function isElysBin(buf: ArrayBuffer | null | undefined): boolean {
  return !!buf && buf.byteLength >= 12 && new TextDecoder().decode(new Uint8Array(buf, 0, 8)) === MAGIC
}

/** 解码 ELYSBIN1：返回 { meta, arrays }；arrays 按 name 取出对应 TypedArray（f4→Float32Array / f8→Float64Array）。 */
export function decodeElysBin(buf: ArrayBuffer): ElysBin {
  const dv = new DataView(buf)
  if (new TextDecoder().decode(new Uint8Array(buf, 0, 8)) !== MAGIC) throw new Error('bad ELYSBIN1 magic')
  const metaLen = dv.getUint32(8, true)
  const meta = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 12, metaLen))) as ElysBin['meta']
  const descs = Array.isArray(meta.arrays) ? meta.arrays : []
  const arrays: Record<string, Float32Array | Float64Array> = {}
  let off = 12 + metaLen
  for (const d of descs) {
    if (d.dtype === 'f8') {
      arrays[d.name] = new Float64Array(buf.slice(off, off + d.count * 8)) // slice 拷进新缓冲，天然 8 字节对齐
      off += d.count * 8
    } else {
      arrays[d.name] = new Float32Array(buf.slice(off, off + d.count * 4))
      off += d.count * 4
    }
  }
  return { meta, arrays }
}
