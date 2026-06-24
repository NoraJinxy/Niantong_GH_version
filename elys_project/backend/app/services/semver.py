"""
Purpose: SemVer (x.y.z) version label validation and comparison utilities.
Related: app/services/dataset_lifecycle.py, docs_v2/3-25.

按 DEC-2026-0531-C: dataset_versions.version_label 强制 SemVer x.y.z 格式。
- major = 实验设计变更（任务范式 / 通道布局 / 采样率）
- minor = 加被试 / 加 session / 加新条件
- patch = 元数据笔误 / 注释修正 / sidecar 补全
- 允许 0.x.y 表示 pre-release / 未稳定
- 不支持 build metadata 或 pre-release 后缀（保持简单，后续需要再扩展）
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# 严格 x.y.z，不允许前导零（除了单独的 0）、不允许 build / pre-release 后缀
_SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class SemVerError(ValueError):
    """SemVer 解析或校验失败。"""


@dataclass(frozen=True, order=True)
class SemVer:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:  # 输出仍是字符串形式
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump_major(self) -> "SemVer":
        return SemVer(self.major + 1, 0, 0)

    def bump_minor(self) -> "SemVer":
        return SemVer(self.major, self.minor + 1, 0)

    def bump_patch(self) -> "SemVer":
        return SemVer(self.major, self.minor, self.patch + 1)


def parse_semver(label: str) -> SemVer:
    """解析 SemVer 字符串。不符合格式抛 SemVerError。"""
    if not isinstance(label, str):
        raise SemVerError(f"版本号必须是字符串，得到 {type(label).__name__}")
    normalized = label.strip()
    match = _SEMVER_RE.match(normalized)
    if match is None:
        raise SemVerError(
            f"版本号必须是 SemVer x.y.z 格式（不允许前导零、后缀或 build 元数据），得到 '{label}'"
        )
    major, minor, patch = match.groups()
    return SemVer(int(major), int(minor), int(patch))


def is_valid_semver(label: str) -> bool:
    """便捷布尔判断。"""
    try:
        parse_semver(label)
    except SemVerError:
        return False
    return True


def compare_semver(a: str, b: str) -> int:
    """比较两个 SemVer 字符串。a < b 返回 -1，相等返回 0，a > b 返回 1。"""
    va = parse_semver(a)
    vb = parse_semver(b)
    if va < vb:
        return -1
    if va > vb:
        return 1
    return 0


def ensure_strictly_newer(*, previous_label: str, new_label: str) -> None:
    """要求 new 严格大于 previous，否则抛 SemVerError。"""
    if compare_semver(new_label, previous_label) <= 0:
        raise SemVerError(
            f"新版本号 {new_label} 必须严格大于已有最新发布版本号 {previous_label}"
        )
