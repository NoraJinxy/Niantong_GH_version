"""
Purpose: 通用数值二进制容器 ELYSBIN1（meta JSON + 若干命名扁平浮点数组），供观察取数端点统一二进制传输。
         比逐数据类型各发明 magic 更省：前端一个 decodeElysBin 通吃，后端各端点只描述自己的数组布局。
         与时域专用的 EEGBIN01（timeseries.encode_timeseries_binary）并存——后者是历史格式、暂不动；
         新接入的 PSD / TFR(cube) / ICA 等统一走本容器。
Related: app/routers/study_outputs.py（各端点 format=binary 分支调用），
         frontend src/composables/observe/binaryCodec.ts（decodeElysBin 解码）。

布局：
  b"ELYSBIN1"            (8 字节 magic)
  u32 metaLen (LE)
  meta(JSON utf8)        含调用方业务字段 + 注入的 arrays:[{name,dtype,count}]（描述后续数组）
  arrays bytes           各数组按 meta.arrays 顺序紧排，小端；dtype f4=float32 / f8=float64
"""

from __future__ import annotations

import json
import struct
from typing import Any, Sequence

_MAGIC = b"ELYSBIN1"


def encode_arrays_binary(meta: dict[str, Any], arrays: Sequence[tuple[str, str, Any]]) -> bytes:
    """meta（JSON 可序列化的业务字段）+ 一组命名浮点数组 → 紧凑二进制。

    arrays: [(name, dtype, values)]，dtype ∈ {"f4","f8"}；values 为 numpy 可接受的一维序列/ndarray。
    meta 里会自动注入 arrays 描述（name/dtype/count），前端据此切分还原；调用方不要自带 "arrays" 键。
    """
    import numpy as np  # noqa: PLC0415

    descs: list[dict[str, Any]] = []
    blobs: list[bytes] = []
    for name, dtype, values in arrays:
        np_dt = "<f4" if str(dtype) == "f4" else "<f8"
        arr = np.ascontiguousarray(np.asarray(values, dtype=np_dt))
        descs.append({"name": str(name), "dtype": "f4" if np_dt == "<f4" else "f8", "count": int(arr.size)})
        blobs.append(arr.tobytes())

    full_meta = {**meta, "arrays": descs}
    meta_bytes = json.dumps(full_meta, ensure_ascii=False).encode("utf-8")

    out = bytearray()
    out += _MAGIC
    out += struct.pack("<I", len(meta_bytes))
    out += meta_bytes
    for blob in blobs:
        out += blob
    return bytes(out)
