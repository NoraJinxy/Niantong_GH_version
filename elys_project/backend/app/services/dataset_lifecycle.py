"""
Purpose: Dataset lifecycle state machine — publish / withdraw-request / withdraw / emergency takedown.
Related: app/services/dataset_bootstrap.py, app/services/dataset_assets.py, app/routers/datasets.py, docs_v2/3-25.

按 docs_v2/3-25 第 3 章状态机：
    unpublished → published      (Asset owner, 强制 SemVer + 脱敏/伦理/版权合规声明)
    published → withdraw_requested  (Asset owner, 必填 reason)
    withdraw_requested → withdrawn  (Admin 审核通过)
    withdraw_requested → published  (Admin 审核拒绝, 回到原状态)
    published → withdrawn  (Admin 紧急下架, 跳过审核, 事后补审计)

withdrawn 是终态。要继续工作必须开新版本 (前向演进, 不是状态回退)。

发布 ≠ 分享：发布只冻结 + 铸 DOI（私有也铸），可见范围默认私有、不自动转共享；
对外开放由负责人在发布后经专门「开放」端点单向决定（只升不降）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    DatasetAsset,
    DatasetPublicizationRequest,
    DatasetVersion,
    DatasetVersionReference,
    DatasetWithdrawalRequest,
    User,
)
from app.services.audit_events import record_audit_event
from app.services.semver import (
    SemVerError,
    ensure_strictly_newer,
    is_valid_semver,
    parse_semver,
)


# 同一 Asset 同时只能有一个「进行中」版本：未发布草稿，或正等审批的撤回。
_OPEN_UNPUBLISHED_STATES = {"unpublished", "withdraw_requested"}


def _notify_referrers_of_withdrawal(
    db: Session,
    *,
    version: DatasetVersion,
    actor: User,
    request: DatasetWithdrawalRequest | None,
    via: str,  # 'approved' | 'emergency'
    now: datetime,
) -> int:
    """Phase 4 (docs_v2/3-25) D: 遍历 dataset_version_references, 给每个引用方写一条 audit notification。

    没有专门的通知中心表, 复用 audit_events 作为信道: action="dataset_version.withdrawn.notification_for_referrer",
    study_id 设为引用方 study_id, 让对应 Study 的成员能查到。

    返回: 通知数量。同时把 request.notification_sent_at 设为 now。
    """
    refs = (
        db.query(DatasetVersionReference)
        .filter(DatasetVersionReference.dataset_version_id == version.id)
        .all()
    )
    sent = 0
    for ref in refs:
        record_audit_event(
            db,
            study_id=ref.referencing_study_id,
            action="dataset_version.withdrawn.notification_for_referrer",
            actor_id=actor.id,
            event_scope="study",
            resource_kind="dataset_version",
            resource_id=version.id,
            resource_label=version.version_label,
            metadata={
                "dataset_asset_id": str(version.dataset_asset_id),
                "via": via,  # 走的审批通过 vs 紧急下架
                "reference_kind": ref.reference_kind,
                "reference_id": str(ref.reference_id),
                "withdrawal_request_id": str(request.id) if request else None,
                "version_doi": version.version_doi,
                "withdraw_reason": version.withdraw_reason,
                "withdrawal_admin_notes": version.withdrawal_admin_notes,
            },
            occurred_at=now,
        )
        sent += 1
    if request is not None:
        request.notification_sent_at = now
    return sent


# ============================================
# Exceptions (路由层把这些翻译成 HTTP 状态码)
# ============================================


class DatasetLifecycleError(Exception):
    """生命周期操作的基类异常。"""


class DatasetLifecyclePermissionError(DatasetLifecycleError):
    """权限不足 → 403。"""


class DatasetLifecycleStateError(DatasetLifecycleError):
    """状态机不允许的转换 → 409。"""


class DatasetLifecycleValidationError(DatasetLifecycleError):
    """输入参数校验失败 → 422。"""


# ============================================
# Create new version (Phase 3 C: Asset 已 published 后新开未发布版本)
# ============================================


@dataclass
class CreateVersionResult:
    dataset_version: DatasetVersion
    dataset_asset: DatasetAsset


def create_new_version(
    db: Session,
    *,
    asset: DatasetAsset,
    actor: User,
    commit: bool = True,
) -> CreateVersionResult:
    """在已发布过版本的 Asset 上创建新的 working 未发布版本（v+1 前向演进）。

    校验:
      - actor 是 asset owner（仅负责人，不含创建者 / 管理员）
      - Asset 当前没有其他未发布或 withdraw_requested 版本 (同时只能有一个 in-progress)
      - Asset 至少已有一个 published / withdrawn 版本 (否则应该走 bootstrap)

    副作用:
      - 新建 DatasetVersion: version_label='working', state='unpublished', qa_status='not_run'
      - storage_uri 用 working slot (上一次 publish 已把它 rename 成 SemVer, working 空出)
      - **不更新 asset.current_version_id** — 其他 Study 仍默认挂稳定的 published 版本
      - 写 dataset_version.unpublished_created 审计

    注意: 物理存储目录创建留给路由层（避免 service 层耦合 settings）。
    """
    # 延迟 import 避免循环
    from app.services.dataset_bootstrap import (
        WORKING_DATASET_VERSION_LABEL,
        dataset_version_storage_uri,
    )

    _ensure_asset_owner(asset, actor)

    open_versions = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state.in_(_OPEN_UNPUBLISHED_STATES),
        )
        .all()
    )
    if open_versions:
        existing_label = open_versions[0].version_label
        raise DatasetLifecycleStateError(
            f"Asset 已有未完结的版本 ({existing_label})，请先发布或处理完毕再新建版本"
        )

    existing_versions = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.dataset_asset_id == asset.id)
        .count()
    )
    if existing_versions == 0:
        raise DatasetLifecycleStateError(
            "Asset 还没有任何版本，请通过 bootstrap 流程创建初始版本"
        )

    version = DatasetVersion(
        dataset_asset_id=asset.id,
        version_label=WORKING_DATASET_VERSION_LABEL,
        state="unpublished",
        qa_status="not_run",
        storage_uri=dataset_version_storage_uri(asset.id),
        metadata_json={"auto_created": True, "source": "create_new_version"},
        created_by=actor.id,
    )
    db.add(version)
    db.flush()

    record_audit_event(
        db,
        action="dataset_version.unpublished_created",
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=version.version_label,
        metadata={
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "trigger": "post_publish_new_version",
        },
    )

    if commit:
        db.commit()
        db.refresh(version)
        db.refresh(asset)

    return CreateVersionResult(dataset_version=version, dataset_asset=asset)


# ============================================
# Publish
# ============================================


@dataclass
class PublishResult:
    dataset_version: DatasetVersion
    dataset_asset: DatasetAsset
    previous_version_label: str  # 发布前的 version_label, 通常是 "working" 或上一个 SemVer
    is_first_published_version: bool


def _ensure_asset_owner(asset: DatasetAsset, user: User) -> None:
    """发布 / 申请撤回 / 开新版本 = 仅负责人（2026-06-09 决策3 / 规则9）。

    严格只放行 owner_id == user.id：**不含创建者、不含管理员**。管理员仅保留撤回审核、
    紧急下架、隔离等平台治理职责，不替负责人做发布/授权/撤回申请。
    """
    if asset.owner_id == user.id:
        return
    raise DatasetLifecyclePermissionError("仅数据集负责人可执行此操作")


def _ensure_admin(user: User) -> None:
    """紧急下架归管理员（2026-06-09 决策A / 规则9，收敛自旧 superadmin 校验）。

    紧急下架属平台治理职责，由管理员执行（不再要求 superadmin）。seed
    （seeds/01_roles_permissions.sql）里 admin 被赋予全部权限、是事实上的最高权限角色。
    `superadmin` 角色另作管理员管理 / 平台治理之用，与数据集生命周期无关。
    """
    if user.has_role("admin"):
        return
    raise DatasetLifecyclePermissionError("紧急下架仅限管理员")


def _latest_published_version_label(db: Session, *, asset: DatasetAsset) -> str | None:
    """取该 Asset 下最大的已发布版本号（按 SemVer 比较），若没有则返回 None。"""
    candidates = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.state == "published",
        )
        .all()
    )
    valid_labels = [v.version_label for v in candidates if is_valid_semver(v.version_label)]
    if not valid_labels:
        return None
    return str(max(parse_semver(label) for label in valid_labels))


def publish_dataset_version(
    db: Session,
    *,
    version: DatasetVersion,
    new_version_label: str,
    actor: User,
    deidentified_confirmed: bool,
    ethics_statement: str,
    license_statement: str,
    commit: bool = True,
) -> PublishResult:
    """把未发布版本发布为 published。

    校验:
      - actor 是 asset owner（仅负责人）
      - version.state 必须是 'unpublished'
      - **合规关口（每次发布都重做，规则3 / 决策4）**：
          deidentified_confirmed 必须为 True（脱敏确认）；
          ethics_statement / license_statement 必须非空（伦理与版权声明）；缺/未确认 → 422
      - new_version_label 必须是合法 SemVer
      - new_version_label 必须严格大于该 Asset 已有最新 published 版本号
      - new_version_label 必须在该 Asset 下唯一 (UNIQUE 约束已在 DB 层保证)

    副作用:
      - version.state = 'published', published_at, published_by 写入
      - version.version_label rename 为 new_version_label (从 'working' 改为 SemVer)
      - asset.current_version_id 指向该版本
      - asset.concept_doi 首次发布时初始化 (内部类 DOI 字符串, Phase 3 暂不接 DataCite)
      - version.version_doi 同步写入（**私有也铸 DOI**，解析到受限落地页，决策M）
      - content_hash 暂留 None, 后续异步任务计算 (Phase 3 后续任务)
      - 写 dataset_version.published 审计事件（含合规声明留痕）
      - **可见范围不变**：发布 ≠ 分享，默认私有、不自动转共享（决策C-1 / 规则2）

    暂未做 (Phase 4):
      - 通知挂载该版本的 Study
      - 引用追踪表写入
    """
    asset = version.dataset_asset
    if asset is None:
        asset = db.query(DatasetAsset).filter(DatasetAsset.id == version.dataset_asset_id).first()
        if asset is None:
            raise DatasetLifecycleStateError("版本对应的 Asset 不存在")

    _ensure_asset_owner(asset, actor)

    if version.state != "unpublished":
        raise DatasetLifecycleStateError(
            f"只有未发布版本可以发布，当前状态: {version.state}"
        )

    # 合规关口（规则3 / 决策4）：发布是 PII / 伦理 / 版权的强制关口，每次发布都要重做。
    if not deidentified_confirmed:
        raise DatasetLifecycleValidationError("发布前必须确认数据已脱敏（去标识）")
    normalized_ethics = (ethics_statement or "").strip()
    if not normalized_ethics:
        raise DatasetLifecycleValidationError("发布前必须填写伦理声明")
    normalized_license = (license_statement or "").strip()
    if not normalized_license:
        raise DatasetLifecycleValidationError("发布前必须填写版权（许可）声明")

    try:
        new_label = str(parse_semver(new_version_label))
    except SemVerError as exc:
        raise DatasetLifecycleValidationError(str(exc)) from exc

    previous_label = _latest_published_version_label(db, asset=asset)
    if previous_label is not None:
        try:
            ensure_strictly_newer(previous_label=previous_label, new_label=new_label)
        except SemVerError as exc:
            raise DatasetLifecycleValidationError(str(exc)) from exc

    # 防御性: 同 asset 下版本号必须唯一 (UNIQUE 约束兜底, 但提前给友好错误)
    existing = (
        db.query(DatasetVersion)
        .filter(
            DatasetVersion.dataset_asset_id == asset.id,
            DatasetVersion.version_label == new_label,
            DatasetVersion.id != version.id,
        )
        .first()
    )
    if existing is not None:
        raise DatasetLifecycleValidationError(
            f"该 Asset 下已存在版本号 {new_label}，请选择更高的版本号"
        )

    previous_version_label_on_this_row = version.version_label
    is_first_published = previous_label is None

    now = datetime.utcnow()
    version.state = "published"
    version.version_label = new_label
    version.published_at = now
    version.published_by = actor.id

    # Version DOI 暂用内部类 DOI 字符串 (Q-2 待定真接 DataCite 时机)。
    # 私有的已发布版本同样铸 DOI（解析到受限落地页，决策M），与「已发布不可删」一致。
    version.version_doi = f"elys:dataset/{asset.id}/v{new_label}"

    asset.current_version_id = version.id
    asset.updated_at = now

    # 发布 ≠ 分享（决策C-1 / 规则2）：发布只冻结 + 铸 DOI，**不改可见范围**。
    # 是否对外开放由负责人在发布后经专门「开放」端点单向决定（只升不降）。

    # Concept DOI 首次发布时初始化
    if is_first_published and not asset.concept_doi:
        asset.concept_doi = f"elys:dataset/{asset.id}"

    record_audit_event(
        db,
        action="dataset_version.published",
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=new_label,
        metadata={
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "previous_version_label": previous_version_label_on_this_row,
            "new_version_label": new_label,
            "is_first_published_version": is_first_published,
            "version_doi": version.version_doi,
            "concept_doi": asset.concept_doi,
            "qa_status": version.qa_status,
            "asset_visibility": asset.visibility,  # 留痕：发布不改可见范围
            # 合规声明留痕（规则3 / 决策4）：每个已发布版本独立、不可变。
            "deidentified_confirmed": True,
            "ethics_statement": normalized_ethics,
            "license_statement": normalized_license,
        },
        occurred_at=now,
    )

    if commit:
        db.commit()
        db.refresh(version)
        db.refresh(asset)

    return PublishResult(
        dataset_version=version,
        dataset_asset=asset,
        previous_version_label=previous_version_label_on_this_row,
        is_first_published_version=is_first_published,
    )


# ============================================
# Withdrawal request (申请撤回 - owner 提交, 待 admin 审核)
# ============================================


def request_version_withdrawal(
    db: Session,
    *,
    version: DatasetVersion,
    reason: str,
    actor: User,
    commit: bool = True,
) -> DatasetWithdrawalRequest:
    """负责人提交撤回申请，version 状态 published → withdraw_requested。

    Admin 审核：通过则 withdrawn，拒绝则回到 published。
    """
    asset = version.dataset_asset
    if asset is None:
        asset = db.query(DatasetAsset).filter(DatasetAsset.id == version.dataset_asset_id).first()
        if asset is None:
            raise DatasetLifecycleStateError("版本对应的 Asset 不存在")

    _ensure_asset_owner(asset, actor)

    if version.state != "published":
        raise DatasetLifecycleStateError(
            f"只有 published 版本可以申请撤回，当前状态: {version.state}"
        )

    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise DatasetLifecycleValidationError("撤回原因不能为空")

    now = datetime.utcnow()
    version.state = "withdraw_requested"
    version.withdraw_requested_at = now
    version.withdraw_requested_by = actor.id
    version.withdraw_reason = normalized_reason

    request = DatasetWithdrawalRequest(
        dataset_version_id=version.id,
        requested_by=actor.id,
        requested_at=now,
        reason=normalized_reason,
    )
    db.add(request)

    record_audit_event(
        db,
        action="dataset_version.withdraw_requested",
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=version.version_label,
        metadata={
            "dataset_asset_id": str(asset.id),
            "dataset_asset_code": asset.code,
            "reason": normalized_reason,
        },
        occurred_at=now,
    )

    if commit:
        db.commit()
        db.refresh(version)
        db.refresh(request)

    return request


# ============================================
# Withdrawal review (admin 审核撤回申请)
# ============================================


def review_withdrawal_request(
    db: Session,
    *,
    request: DatasetWithdrawalRequest,
    decision: str,
    admin_notes: str | None,
    actor: User,
    commit: bool = True,
) -> DatasetWithdrawalRequest:
    """管理员审核撤回申请。decision = 'approved' | 'rejected'。

    approved → version.state = withdrawn (终态)
    rejected → version.state = published (回到原状态), 清空 withdraw_requested_* 字段
    """
    if not actor.has_role("admin"):
        raise DatasetLifecyclePermissionError("仅平台管理员可审核撤回申请")

    if decision not in {"approved", "rejected"}:
        raise DatasetLifecycleValidationError("审核结果必须是 approved 或 rejected")

    if request.decision is not None:
        raise DatasetLifecycleStateError(
            f"该撤回申请已审核，结果: {request.decision}"
        )

    version = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.id == request.dataset_version_id)
        .first()
    )
    if version is None:
        raise DatasetLifecycleStateError("撤回申请对应的版本不存在")

    if version.state != "withdraw_requested":
        raise DatasetLifecycleStateError(
            f"版本当前状态不允许审核: {version.state}"
        )

    now = datetime.utcnow()
    request.decision = decision
    request.reviewed_by = actor.id
    request.reviewed_at = now
    request.admin_notes = (admin_notes or "").strip() or None

    notified_count = 0
    if decision == "approved":
        version.state = "withdrawn"
        version.withdrawn_at = now
        version.withdrawn_by = actor.id
        version.withdrawal_admin_notes = request.admin_notes
        action = "dataset_version.withdrawn"
    else:  # rejected
        version.state = "published"
        version.withdraw_requested_at = None
        version.withdraw_requested_by = None
        version.withdraw_reason = None
        action = "dataset_version.withdraw_rejected"

    record_audit_event(
        db,
        action=action,
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=version.version_label,
        metadata={
            "dataset_asset_id": str(version.dataset_asset_id),
            "withdrawal_request_id": str(request.id),
            "decision": decision,
            "admin_notes": request.admin_notes,
            "original_reason": request.reason,
        },
        occurred_at=now,
    )

    # Phase 4 (docs_v2/3-25) D: 通过撤回时通知所有引用方
    if decision == "approved":
        notified_count = _notify_referrers_of_withdrawal(
            db, version=version, actor=actor, request=request, via="approved", now=now,
        )

    if commit:
        db.commit()
        db.refresh(version)
        db.refresh(request)

    return request


# ============================================
# Emergency takedown (DEC-2026-0531-D)
# ============================================


def emergency_takedown_version(
    db: Session,
    *,
    version: DatasetVersion,
    reason: str,
    actor: User,
    commit: bool = True,
) -> DatasetWithdrawalRequest:
    """管理员紧急下架, 跳过审核流程, 直接 published → withdrawn。

    必须事后补审计 (DEC-2026-0531-D): 创建一条 decision='emergency' 的 DatasetWithdrawalRequest。
    """
    _ensure_admin(actor)

    if version.state not in {"published", "withdraw_requested"}:
        raise DatasetLifecycleStateError(
            f"紧急下架仅适用于 published 或 withdraw_requested 状态, 当前: {version.state}"
        )

    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise DatasetLifecycleValidationError("紧急下架必须填写原因（事后审计需要）")

    now = datetime.utcnow()
    version.state = "withdrawn"
    version.withdrawn_at = now
    version.withdrawn_by = actor.id
    version.withdrawal_admin_notes = normalized_reason

    # 若该版本本就有一条等审批的撤回申请（decision 为空），紧急下架会让它的版本状态不再是
    # withdraw_requested、正常 review 会 409。必须把它一并关闭（标 emergency），否则它会永远
    # 挂在管理员 /pending 待审列表里、点也点不动。
    stale_pending = (
        db.query(DatasetWithdrawalRequest)
        .filter(
            DatasetWithdrawalRequest.dataset_version_id == version.id,
            DatasetWithdrawalRequest.decision.is_(None),
        )
        .all()
    )
    for pending in stale_pending:
        pending.decision = "emergency"
        pending.reviewed_by = actor.id
        pending.reviewed_at = now
        pending.admin_notes = (pending.admin_notes or "") + "（已被紧急下架接管）"

    request = DatasetWithdrawalRequest(
        dataset_version_id=version.id,
        requested_by=actor.id,
        requested_at=now,
        reason=normalized_reason,
        reviewed_by=actor.id,
        reviewed_at=now,
        decision="emergency",
        admin_notes=normalized_reason,
    )
    db.add(request)
    db.flush()  # id 由 DB server_default 生成，flush 后才有值供审计/通知引用

    record_audit_event(
        db,
        action="dataset_version.emergency_takedown",
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_version",
        resource_id=version.id,
        resource_label=version.version_label,
        metadata={
            "dataset_asset_id": str(version.dataset_asset_id),
            "reason": normalized_reason,
            "withdrawal_request_id": str(request.id),
        },
        occurred_at=now,
    )

    # Phase 4 (docs_v2/3-25) D: 紧急下架同样通知所有引用方
    _notify_referrers_of_withdrawal(
        db, version=version, actor=actor, request=request, via="emergency", now=now,
    )

    if commit:
        db.commit()
        db.refresh(version)
        db.refresh(request)

    return request


# ============================================
# Publicization request (shared → public 转公开审核，2026-06-10 Q1 定稿)
# ============================================
# 发布 = 自助（即时冻结 + DOI，可见范围 private/shared，无审核）；转公开 = 先审后开：
# shared → public 是唯一真实曝光（全网可搜），需管理员批准。private 是邀请制基础，shared 是
# 邀请制协作（都不算全网曝光），经 open-visibility 自助升级；只有升到 public 走本审核。
# 调试期默认 auto-approve（无人工审核策略时自动通过、decision='auto'、即时生效）。

# 调试期默认自动通过；上线改 False（或接入 settings 开关）后转公开走管理员人工审核队列。
PUBLICIZATION_AUTO_APPROVE = True


def request_publicization(
    db: Session,
    *,
    asset: DatasetAsset,
    actor: User,
    reason: str | None = None,
    commit: bool = True,
) -> DatasetPublicizationRequest:
    """负责人申请把数据集可见范围升到 public（shared → public）。

    调试期（PUBLICIZATION_AUTO_APPROVE=True）：直接升 public、decision='auto'、即时生效。
    生产（False）：留 pending，等管理员 review_publicization_request 审核。
    private 请先经 open-visibility 升到 shared（邀请制协作，不算全网曝光，自助）。
    """
    _ensure_asset_owner(asset, actor)

    if asset.visibility == "public":
        raise DatasetLifecycleStateError("该数据集已是 public")
    if asset.visibility != "shared":
        raise DatasetLifecycleStateError(
            "仅 shared 可见范围可申请转公开；private 请先开放为 shared（邀请制协作）"
        )
    if _latest_published_version_label(db, asset=asset) is None:
        raise DatasetLifecycleStateError(
            "资产尚无已发布版本，无可公开内容；请先发布至少一个版本"
        )

    # 同一资产同时只允许一个待审转公开申请。
    existing_pending = (
        db.query(DatasetPublicizationRequest)
        .filter(
            DatasetPublicizationRequest.asset_id == asset.id,
            DatasetPublicizationRequest.decision.is_(None),
        )
        .first()
    )
    if existing_pending is not None:
        raise DatasetLifecycleStateError("该数据集已有一个待审核的转公开申请")

    now = datetime.utcnow()
    normalized_reason = (reason or "").strip() or None
    request = DatasetPublicizationRequest(
        asset_id=asset.id,
        requested_by=actor.id,
        requested_at=now,
        reason=normalized_reason,
    )
    db.add(request)

    record_audit_event(
        db,
        action="dataset_asset.publicize_requested",
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={"dataset_asset_code": asset.code, "reason": normalized_reason},
        occurred_at=now,
    )

    if PUBLICIZATION_AUTO_APPROVE:
        # 调试期：无人工审核策略，自动通过并即时升 public，decision='auto' 留痕。
        request.decision = "auto"
        request.reviewed_by = actor.id
        request.reviewed_at = now
        request.admin_notes = "调试期自动通过（无人工审核策略）"
        old_visibility = asset.visibility
        asset.visibility = "public"
        asset.updated_at = now
        record_audit_event(
            db,
            action="dataset_asset.publicized",
            actor_id=actor.id,
            event_scope="dataset_asset",
            resource_kind="dataset_asset",
            resource_id=asset.id,
            resource_label=asset.name,
            metadata={
                "old_visibility": old_visibility,
                "new_visibility": "public",
                "decision": "auto",
                "publicization_request_id": str(request.id),
            },
            occurred_at=now,
        )

    if commit:
        db.commit()
        db.refresh(asset)
        db.refresh(request)

    return request


def review_publicization_request(
    db: Session,
    *,
    request: DatasetPublicizationRequest,
    decision: str,
    admin_notes: str | None,
    actor: User,
    commit: bool = True,
) -> DatasetPublicizationRequest:
    """管理员审核转公开申请。approved → asset.visibility=public；rejected → 保持 shared。"""
    _ensure_admin(actor)

    if decision not in {"approved", "rejected"}:
        raise DatasetLifecycleValidationError("审核结果必须是 approved 或 rejected")
    if request.decision is not None:
        raise DatasetLifecycleStateError(f"该转公开申请已审核，结果: {request.decision}")

    asset = db.query(DatasetAsset).filter(DatasetAsset.id == request.asset_id).first()
    if asset is None:
        raise DatasetLifecycleStateError("转公开申请对应的资产不存在")

    now = datetime.utcnow()
    request.decision = decision
    request.reviewed_by = actor.id
    request.reviewed_at = now
    request.admin_notes = (admin_notes or "").strip() or None

    old_visibility = asset.visibility
    if decision == "approved":
        asset.visibility = "public"
        asset.updated_at = now
        action = "dataset_asset.publicized"
    else:
        action = "dataset_asset.publicize_rejected"

    record_audit_event(
        db,
        action=action,
        actor_id=actor.id,
        event_scope="dataset_asset",
        resource_kind="dataset_asset",
        resource_id=asset.id,
        resource_label=asset.name,
        metadata={
            "old_visibility": old_visibility,
            "new_visibility": asset.visibility,
            "decision": decision,
            "admin_notes": request.admin_notes,
            "publicization_request_id": str(request.id),
        },
        occurred_at=now,
    )

    if commit:
        db.commit()
        db.refresh(asset)
        db.refresh(request)

    return request
