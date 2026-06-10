"""
Purpose: 节点保存设置统一计算 —— 把 NodeSpec 的 save 子对象（step_label /
         auto_tags / name_template / dynamic_tags）与拓扑角色 (leaf /
         intermediate) + BIDS 实体 + 用户参数合成最终
         {display_name, tags, retention_status, retention_expires_at}，
         注入到 StudyOutput metadata。

设计目标:
- 取消 Save 节点：每个处理节点的产物在 dispatcher 阶段就决定好名字 / 标签 / 保留期；
- 模板渲染允许 {subject} {task} {condition} {node_title} 等占位符；
- 自动 tag 前缀 step:* / type:* / cond:* 由 spec 写死；用户额外加的 tag 与之合并；
- display_name 冲突时自动加 (2) (3) 后缀（无配对中转事务，单 execution 内事务可见）；
- retention 默认由拓扑决定 —— leaf=current(永久) / intermediate=cached(7 天)；
  用户可在节点参数里通过 `retention` 显式覆盖。

Related:
- app/pipeline/nodes/*.json (save 子对象)
- app/pipeline/topology.py (拓扑角色)
- app/pipeline/dispatcher.py (调用入口)
- app/pipeline/artifacts.py (写 study_outputs 行)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any

from app.pipeline.topology import ROLE_INTERMEDIATE


_TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

# 中间节点的默认缓存保留天数（cleanup task 在到期后清理磁盘文件）
DEFAULT_INTERMEDIATE_RETENTION_DAYS = 7


def render_template(template: str, ctx: dict[str, Any]) -> str:
    """渲染模板字符串，支持 {subject} {task} {session} {run} {condition}
    {node_title} {step_label} {data_type} {index} {bids_subject_id} 等占位符。

    缺失变量回落为 '{name?}' 字面值（不抛错，便于夜班批处理不被一个缺字段炸掉）。
    模板为空时返回空串。
    """
    if not template:
        return ""

    def resolve(name: str) -> str:
        if name == "subject":
            value = (
                ctx.get("subject")
                or ctx.get("bids_subject_id")
                or ctx.get("subject_id")
            )
            return str(value) if value else "{subject?}"
        if name == "bids_subject_id":
            value = ctx.get("bids_subject_id") or ctx.get("subject")
            return str(value) if value else "{bids_subject_id?}"
        if name == "index":
            value = ctx.get("index")
            return str(value) if value is not None else "{index?}"
        value = ctx.get(name)
        if value in (None, ""):
            return f"{{{name}?}}"
        return str(value)

    return _TEMPLATE_PATTERN.sub(lambda match: resolve(match.group(1)), template)


def merge_tags(*sources: Any, ctx: dict[str, Any] | None = None) -> list[str]:
    """合并多个 tag 来源，去重 + 保序 + 剔除空串。

    每个来源可以是 None / str / list[str]；str 会按逗号拆分。
    含模板占位符的 tag 会用 ctx 渲染。
    """
    seen: set[str] = set()
    result: list[str] = []
    for source in sources:
        if source is None:
            continue
        if isinstance(source, str):
            items = [piece.strip() for piece in source.split(",")]
        elif isinstance(source, (list, tuple, set)):
            items = [str(item).strip() for item in source]
        else:
            items = [str(source).strip()]
        for raw in items:
            if not raw:
                continue
            if "{" in raw and ctx is not None:
                rendered = render_template(raw, ctx)
            else:
                rendered = raw
            rendered = rendered.strip()
            if not rendered or rendered in seen:
                continue
            seen.add(rendered)
            result.append(rendered)
    return result


def resolve_display_name_conflict(
    db: Any,
    study_id: Any,
    base_name: str,
) -> str:
    """查同 study_id 下是否已有同名活跃 study_output，若有则自动加 (2) (3) 后缀。

    匹配规则:
      - 排除 deleted_at IS NOT NULL 的行
      - 排除 retention_status = 'none' 的行（不应保留的不参与冲突）
      - 命中 display_name = base 或 display_name LIKE 'base (N)'

    返回:
      - 无冲突 → base 原样
      - 有冲突 → "base (N)"，N 是当前未占用的最小整数 ≥2
    """
    if not base_name:
        return base_name

    # 延迟导入避免循环：本模块被 dispatcher 加载时 app.models 链已就绪
    from app.models import StudyOutput
    from sqlalchemy import or_

    base = base_name.strip()
    if not base:
        return base_name

    # 转义 LIKE 通配符（防止 base 自身含 % 或 _）
    escaped = base.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    like_pattern = f"{escaped} (%)"

    rows = (
        db.query(StudyOutput.display_name)
        .filter(
            StudyOutput.study_id == study_id,
            StudyOutput.deleted_at.is_(None),
            StudyOutput.retention_status != "none",
            or_(
                StudyOutput.display_name == base,
                StudyOutput.display_name.like(like_pattern, escape="\\"),
            ),
        )
        .all()
    )

    used: set[int] = set()
    base_exists = False
    suffix_pattern = re.compile(re.escape(base) + r" \((\d+)\)$")
    for row in rows:
        # SQLAlchemy 2.x 的 Row 不继承 tuple，但永远支持 row[0] indexing；
        # 测试 mock 也按 tuple 形式给 (name,)。统一用 row[0]。
        name = row[0] if row is not None else None
        if not name or not isinstance(name, str):
            continue
        if name == base:
            base_exists = True
            continue
        match = suffix_pattern.match(name)
        if match:
            used.add(int(match.group(1)))

    if not base_exists and not used:
        return base

    # 找下一个未占用的 N（从 2 开始）
    n = 2
    while n in used:
        n += 1
    return f"{base} ({n})"


def default_retention_for_role(role: str | None) -> tuple[str, datetime | None]:
    """根据拓扑角色返回 (retention_status, retention_expires_at)。

    - leaf → ("current", None)            保留，用户在结果页可见
    - intermediate → ("cached", now+7d)   临时存盘供 cache/重启续跑用，7 天后清理
    - 其他 / None → ("current", None)     保守默认
    """
    if role == ROLE_INTERMEDIATE:
        return "cached", datetime.utcnow() + timedelta(days=DEFAULT_INTERMEDIATE_RETENTION_DAYS)
    return "current", None


def _normalise_retention_param(value: Any) -> str | None:
    """把用户参数里的 retention override 标准化为 'current' / 'pinned' / 'none' / None。"""
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"current", "pinned", "none"}:
        return text
    # 兼容旧 NodeSpec 的 "study" / "temporary" 字面值
    if text in {"study", "permanent", "keep"}:
        return "current"
    if text in {"temporary", "trash"}:
        return "none"
    if text in {"cache", "cached"}:
        return None  # 走拓扑默认（cached 7d）
    return None


def apply_save_settings(
    *,
    db: Any,
    study_id: Any,
    node: dict[str, Any],
    node_spec: dict[str, Any] | None,
    params: dict[str, Any] | None,
    topology: dict[str, str] | None,
    bids_entities: dict[str, Any] | None = None,
    split_value: str | None = None,
    index: int = 0,
) -> dict[str, Any]:
    """组合 spec.save + 拓扑 + BIDS + 用户参数，返回保存配置 dict。

    返回键:
      display_name              冲突已自动解决的最终名字
      tags                      list[str]，已合并 auto/dynamic/user，保序去重
      retention_status          'current' / 'cached' / 'pinned' / 'none'
      retention_expires_at      datetime 或 None
      step_label                来自 spec.save.step_label（透传给 metadata）
      data_type                 来自 spec.save.data_type（透传给 metadata）

    dispatcher 应该把这个 dict 合并进 metadata，让 artifacts._register_artifact
    接管写入。
    """
    save_cfg = ((node_spec or {}).get("save") or {})
    node_id = str(node.get("id") or "")
    node_type = str(node.get("type") or "")
    node_title = str(node.get("title") or save_cfg.get("step_label") or node_type).strip()
    params = params or {}
    bids = bids_entities or {}
    role = (topology or {}).get(node_id)

    # 1) 构造渲染上下文（subject 多源回退）
    ctx: dict[str, Any] = {
        "node_title": node_title,
        "node_id": node_id,
        "node_type": node_type,
        "step_label": save_cfg.get("step_label", ""),
        "data_type": save_cfg.get("data_type", ""),
        "subject": bids.get("bids_subject_id") or bids.get("subject") or bids.get("subject_id"),
        "bids_subject_id": bids.get("bids_subject_id") or bids.get("subject"),
        "task": bids.get("task"),
        "session": bids.get("session"),
        "run": bids.get("run") or bids.get("run_label"),
        "condition": split_value or bids.get("condition"),
        "index": index + 1,
    }

    # 2) 选模板（用户 override > spec.split 模板 > spec.default 模板 > 兜底）
    user_template_raw = params.get("display_name_template") or params.get("display_name")
    user_template = str(user_template_raw or "").strip()
    if split_value:
        spec_template = save_cfg.get("name_template_default_split") or save_cfg.get("name_template_default")
    else:
        spec_template = save_cfg.get("name_template_default")
    template = user_template or spec_template or "{subject}_{task}_{node_title}"
    rendered_base = render_template(template, ctx).strip()
    if not rendered_base:
        rendered_base = f"{node_title or 'node'}-{index + 1}"

    # 3) 冲突检测自动 (N)
    display_name = resolve_display_name_conflict(db, study_id, rendered_base)

    # 4) 合并 tags：auto_tags + dynamic_tags(when split/always) + user_tags
    auto_tags = save_cfg.get("auto_tags", [])
    dynamic_tags: list[str] = []
    if save_cfg.get("always_per_condition"):
        dynamic_tags = list(save_cfg.get("dynamic_tags_always", []) or [])
    elif split_value:
        dynamic_tags = list(save_cfg.get("dynamic_tags_when_split", []) or [])
    user_tags = params.get("tags")
    tags = merge_tags(auto_tags, dynamic_tags, user_tags, ctx=ctx)

    # 5) Retention：用户 override > 拓扑默认
    retention_override = _normalise_retention_param(params.get("retention"))
    if retention_override == "current":
        retention_status, retention_expires_at = "current", None
    elif retention_override == "pinned":
        retention_status, retention_expires_at = "pinned", None
    elif retention_override == "none":
        # "不保留"映射到合法的 'temporary'（expires 为空 → 下次 cleanup 立即可回收）。
        # 不能写 'none'：study_outputs.retention_status 的 CHECK 只允许
        # current/pinned/cached/temporary/deleted/quarantined，写 'none' 会撞约束、
        # 整个节点产物登记失败。
        retention_status, retention_expires_at = "temporary", None
    else:
        retention_status, retention_expires_at = default_retention_for_role(role)

    return {
        "display_name": display_name,
        "tags": tags,
        "retention_status": retention_status,
        "retention_expires_at": retention_expires_at,
        "step_label": save_cfg.get("step_label"),
        "data_type": save_cfg.get("data_type"),
    }


__all__ = [
    "render_template",
    "merge_tags",
    "resolve_display_name_conflict",
    "default_retention_for_role",
    "apply_save_settings",
    "DEFAULT_INTERMEDIATE_RETENTION_DAYS",
]
