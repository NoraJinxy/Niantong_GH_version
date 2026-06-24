"""
Purpose: Manage platform-level Dataset assets and Study mount records.
Related: app/models/study.py, app/routers/datasets.py, docs_v2/3-00 and docs_v2/7-30.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models import (
    DatasetAsset,
    DatasetMember,
    Recording,
    DatasetVersion,
    DatasetVersionReference,
    Study,
    StudyDatasetMount,
    StudyMember,
    User,
)


class DatasetAssetConflictError(Exception):
    pass


class DatasetMountStateError(Exception):
    """关联（Link）操作违反生命周期状态 / 可见性约束（3-25）。"""


def working_dataset_asset_code(study: Study) -> str:
    return f"study-{study.id}-working"


# UI Phase (docs_v2/6-05): 数据集概要聚合 — 给前端 L1 区域显示
def compute_asset_stats(db: Session, asset_ids: list) -> dict:
    """批量聚合多个 Asset 的概要统计：被试数、任务列表、总时长、最后导入时间。

    返回 {asset_id_str: {"subject_count": int, "task_codes": list[str],
                          "total_duration_seconds": float, "last_imported_at": datetime|None}}

    单 query 聚合，避免 N+1。空 asset_ids 直接返回 {}。
    """
    if not asset_ids:
        return {}

    # 被试数 + 总时长 + 最后导入时间（单查询多聚合）
    rows = (
        db.query(
            Recording.dataset_asset_id.label("asset_id"),
            func.count(func.distinct(Recording.subject_id)).label("subject_count"),
            func.count(Recording.id).label("recording_count"),
            func.coalesce(func.sum(Recording.duration_seconds), 0.0).label("total_duration"),
            func.max(Recording.imported_at).label("last_imported_at"),
        )
        .filter(Recording.dataset_asset_id.in_(asset_ids))
        .group_by(Recording.dataset_asset_id)
        .all()
    )

    # 任务列表（需要 distinct，另查一次以便 list 化）
    task_rows = (
        db.query(Recording.dataset_asset_id, Recording.task)
        .filter(Recording.dataset_asset_id.in_(asset_ids))
        .distinct()
        .all()
    )
    task_map: dict = {}
    for asset_id, task in task_rows:
        key = str(asset_id)
        if not task:
            continue
        task_map.setdefault(key, []).append(task)

    result: dict = {}
    for asset_id in asset_ids:
        key = str(asset_id)
        result[key] = {
            "subject_count": 0,
            "recording_count": 0,
            "task_codes": sorted(task_map.get(key, [])),
            "total_duration_seconds": 0.0,
            "last_imported_at": None,
        }
    for row in rows:
        key = str(row.asset_id)
        result[key]["subject_count"] = int(row.subject_count or 0)
        result[key]["recording_count"] = int(row.recording_count or 0)
        result[key]["total_duration_seconds"] = float(row.total_duration or 0.0)
        result[key]["last_imported_at"] = row.last_imported_at

    return result


def create_dataset_asset(
    db: Session,
    *,
    name: str,
    code: str,
    owner_id,
    created_by,
    description: str | None = None,
    visibility: str = "private",
    metadata_json: dict[str, Any] | None = None,
    primary_study_id: str | None = None,
) -> DatasetAsset:
    existing = db.query(DatasetAsset).filter(DatasetAsset.code == code).first()
    if existing is not None:
        raise DatasetAssetConflictError(f"Dataset asset code already exists: {code}")
    asset = DatasetAsset(
        name=name,
        code=code,
        description=description,
        owner_id=owner_id,
        status="working",
        visibility=visibility,
        metadata_json=metadata_json or {},
        # 主研究项（primary study）：unpublished 时必填；published 后保留作出身记录（3-25）
        primary_study_id=primary_study_id,
        created_by=created_by,
    )
    db.add(asset)
    db.flush()
    return asset


def get_or_create_working_dataset_asset(
    db: Session,
    *,
    study: Study,
    user: User,
    mount_name: str = "working",
) -> DatasetAsset:
    code = working_dataset_asset_code(study)
    asset = db.query(DatasetAsset).filter(DatasetAsset.code == code).first()
    if asset is None:
        asset = DatasetAsset(
            name=f"{study.name} Working Dataset",
            code=code,
            description="Auto-created working Dataset Asset for Study uploads.",
            owner_id=study.owner_id,
            status="working",
            visibility="private",
            metadata_json={"auto_created": True, "study_id": study.id, "source": "upload"},
            created_by=user.id,
        )
        db.add(asset)
        db.flush()

    existing_mount = (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.study_id == study.id, StudyDatasetMount.mount_name == mount_name)
        .first()
    )
    if existing_mount is None:
        db.add(
            StudyDatasetMount(
                study_id=study.id,
                dataset_asset_id=asset.id,
                mount_name=mount_name,
                selection_json={},
                is_active=True,
                mounted_by=user.id,
            )
        )
        db.flush()
    elif existing_mount.dataset_asset_id != asset.id:
        raise DatasetAssetConflictError(
            f"Study mount name '{mount_name}' already points to another Dataset Asset; "
            "rename that mount or choose an explicit upload target."
        )
    elif not existing_mount.is_active:
        existing_mount.is_active = True
        db.flush()
    return asset


def _is_primary_study_member(db: Session, *, study_id: str | None, user: User) -> bool:
    """user 是否为某研究项的成员（含负责人）。

    判据：研究项负责人（owner_id），或在 study_members 里有一行。
    private 可见档据此放行——「私有 = 负责人 + 管理员 + 主研究项成员」（3-25 规则 6）。
    """
    if study_id is None:
        return False
    owner_id = (
        db.query(Study.owner_id)
        .filter(Study.id == study_id)
        .scalar()
    )
    if owner_id is not None and owner_id == user.id:
        return True
    return (
        db.query(StudyMember.id)
        .filter(
            StudyMember.study_id == study_id,
            StudyMember.user_id == user.id,
            StudyMember.can_read.is_(True),
        )
        .first()
        is not None
    )


def is_user_authorized(db: Session, asset: DatasetAsset, user: User) -> bool:
    """user 是否在该资产的 dataset_members 授权名单里（shared 邀请制，3-25 规则 7）。"""
    return (
        db.query(DatasetMember.id)
        .filter(DatasetMember.asset_id == asset.id, DatasetMember.user_id == user.id)
        .first()
        is not None
    )


def can_read_dataset_asset(db: Session, user: User, asset: DatasetAsset) -> bool:
    """资产读权限（3-25 §1.4 可见范围轴）。

    deleted → False；quarantined → 仅管理员；管理员 / 负责人 / 创建者 → True；
    主研究项成员 → True（规则 6）；public → 任意注册用户 True（规则 8）；
    shared → 仅 dataset_members 授权用户 True（规则 7，邀请制）；否则 False。
    """
    if asset.status == "deleted":
        return False
    if asset.status == "quarantined":
        return user.has_role("admin")
    if user.has_role("admin"):
        return True
    if asset.owner_id == user.id or asset.created_by == user.id:
        return True
    if _is_primary_study_member(db, study_id=asset.primary_study_id, user=user):
        return True
    if asset.visibility == "public":
        return True
    if asset.visibility == "shared" and is_user_authorized(db, asset, user):
        return True
    return False


def can_write_dataset_asset(user: User, asset: DatasetAsset, /) -> bool:
    if asset.status != "working":
        return False
    if user.has_role("admin"):
        return True
    return asset.owner_id == user.id or asset.created_by == user.id


def list_visible_dataset_assets(db: Session, *, user: User) -> list[DatasetAsset]:
    """与 can_read_dataset_asset 同口径列出可见资产（dashboard 计数随之对齐）。"""
    query = db.query(DatasetAsset).filter(DatasetAsset.status != "deleted")
    if user.has_role("admin"):
        return query.order_by(DatasetAsset.created_at.desc(), DatasetAsset.id.desc()).all()

    # 当前用户作为成员（含负责人）的研究项 id 集合 —— 用于「主研究项成员可见」
    member_study_ids = {
        row[0]
        for row in (
            db.query(StudyMember.study_id)
            .filter(StudyMember.user_id == user.id, StudyMember.can_read.is_(True))
            .all()
        )
    }
    member_study_ids.update(
        row[0]
        for row in (
            db.query(Study.id).filter(Study.owner_id == user.id).all()
        )
    )
    # 当前用户被授权（dataset_members）的资产 id 集合 —— 用于「shared 邀请制」
    authorized_asset_ids = {
        row[0]
        for row in (
            db.query(DatasetMember.asset_id)
            .filter(DatasetMember.user_id == user.id)
            .all()
        )
    }

    conditions = [
        DatasetAsset.owner_id == user.id,
        DatasetAsset.created_by == user.id,
        DatasetAsset.visibility == "public",
    ]
    if member_study_ids:
        conditions.append(DatasetAsset.primary_study_id.in_(member_study_ids))
    if authorized_asset_ids:
        conditions.append(
            (DatasetAsset.visibility == "shared") & DatasetAsset.id.in_(authorized_asset_ids)
        )

    return (
        query.filter(
            DatasetAsset.status != "quarantined",
            or_(*conditions),
        )
        .order_by(DatasetAsset.created_at.desc(), DatasetAsset.id.desc())
        .all()
    )


def get_dataset_asset_for_user(db: Session, *, asset_id: UUID, user: User) -> DatasetAsset | None:
    asset = db.query(DatasetAsset).filter(DatasetAsset.id == asset_id).first()
    if asset is None or not can_read_dataset_asset(db, user, asset):
        return None
    return asset


def list_members(db: Session, *, asset: DatasetAsset) -> list[DatasetMember]:
    """列出资产的 dataset_members 授权名单（仅 owner 调用，鉴权在路由层）。"""
    return (
        db.query(DatasetMember)
        .filter(DatasetMember.asset_id == asset.id)
        .order_by(DatasetMember.granted_at.asc(), DatasetMember.id.asc())
        .all()
    )


def grant_member(
    db: Session, *, asset: DatasetAsset, user_id, granted_by
) -> DatasetMember:
    """授权一个用户访问该资产（shared 邀请制）。幂等：已授权则原样返回。"""
    existing = (
        db.query(DatasetMember)
        .filter(DatasetMember.asset_id == asset.id, DatasetMember.user_id == user_id)
        .first()
    )
    if existing is not None:
        return existing
    member = DatasetMember(
        asset_id=asset.id,
        user_id=user_id,
        granted_by=granted_by,
    )
    db.add(member)
    db.flush()
    return member


def revoke_member(db: Session, *, asset: DatasetAsset, user_id) -> bool:
    """取消某用户的授权。返回是否确有一行被删。"""
    member = (
        db.query(DatasetMember)
        .filter(DatasetMember.asset_id == asset.id, DatasetMember.user_id == user_id)
        .first()
    )
    if member is None:
        return False
    db.delete(member)
    db.flush()
    return True


def _resolve_actor_id(actor):
    """把传入的 actor 归一为用户 id：接受 User 对象或裸 UUID。"""
    if actor is None:
        return None
    return getattr(actor, "id", actor)


def _ensure_version_mountable(
    db: Session,
    *,
    dataset_asset: DatasetAsset,
    dataset_version_id,
    target_study_id: str,
    actor=None,
) -> None:
    """关联（Link）版本的状态 + 可见性网关（3-25 §1.6 规则 10/12/13）。

    发布状态门槛：
    - withdraw_requested / withdrawn：拒绝新关联（已有关联在撤回时保留，不接受新增）。
    - unpublished：仅主研究项可关联；其他研究项须等版本发布。
    可见性网关（仅 published 且跨研究项时生效，规则 13）：
    - public：任何研究项可关联。
    - shared：仅当 actor 在 dataset_members 授权名单里才可关联。
    - private：仅主研究项；非主研究项一律拒绝。
    """
    if dataset_version_id is None:
        return  # 兼容期 nullable，Phase 5 起转为必填
    version = (
        db.query(DatasetVersion)
        .filter(DatasetVersion.id == dataset_version_id)
        .first()
    )
    if version is None:
        raise DatasetMountStateError("指定的数据集版本不存在")
    if version.dataset_asset_id != dataset_asset.id:
        raise DatasetMountStateError("数据集版本与 Asset 不匹配")
    if version.state in {"withdraw_requested", "withdrawn"}:
        raise DatasetMountStateError(
            f"版本 {version.version_label} 处于「{version.state}」状态，不能创建新关联；"
            "已有关联保留，但撤回审核中 / 已撤回的版本不接受新关联"
        )
    primary_study_id = dataset_asset.primary_study_id
    is_primary_target = primary_study_id is not None and primary_study_id == target_study_id
    if version.state == "unpublished":
        if not is_primary_target:
            raise DatasetMountStateError(
                f"版本 {version.version_label} 尚未发布，仅主研究项可关联；"
                "请先发布该版本（POST /api/v1/dataset-versions/{id}/publish）"
            )
        return
    # version.state == "published"：跨研究项时按可见范围放行
    if is_primary_target:
        return
    if dataset_asset.visibility == "public":
        return
    if dataset_asset.visibility == "shared":
        actor_id = _resolve_actor_id(actor)
        authorized = actor_id is not None and (
            db.query(DatasetMember.id)
            .filter(DatasetMember.asset_id == dataset_asset.id, DatasetMember.user_id == actor_id)
            .first()
            is not None
        )
        if authorized:
            return
        raise DatasetMountStateError(
            "该数据集为共享（邀请制）且非主研究项，需先获得负责人授权才能关联"
        )
    # private 且非主研究项
    raise DatasetMountStateError(
        "该数据集为私有，仅主研究项可关联；如需他人使用请由负责人开放可见范围或加入主研究项团队"
    )


def mount_dataset_asset_to_study(
    db: Session,
    *,
    study: Study,
    dataset_asset: DatasetAsset,
    mount_name: str,
    mounted_by,
    selection_json: dict[str, Any] | None = None,
    is_active: bool = True,
    dataset_version_id=None,
) -> StudyDatasetMount:
    existing = (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.study_id == study.id, StudyDatasetMount.mount_name == mount_name)
        .first()
    )
    if existing is not None:
        raise DatasetAssetConflictError(f"Study dataset mount name already exists: {mount_name}")

    # 3-25 规则 10/12/13：校验版本发布状态 + 跨研究项可见性网关（actor = 发起关联者）
    _ensure_version_mountable(
        db,
        dataset_asset=dataset_asset,
        dataset_version_id=dataset_version_id,
        target_study_id=study.id,
        actor=mounted_by,
    )

    mount = StudyDatasetMount(
        study_id=study.id,
        dataset_asset_id=dataset_asset.id,
        # Phase 2 (docs_v2/3-25): 挂载锁定到具体版本；Phase 3 起非空
        dataset_version_id=dataset_version_id,
        mount_name=mount_name,
        selection_json=selection_json or {},
        is_active=is_active,
        mounted_by=mounted_by,
    )
    db.add(mount)
    db.flush()

    # Phase 4 (docs_v2/3-25) D: 自动登记引用追踪，撤回时遍历此表通知引用方
    if dataset_version_id is not None:
        record_dataset_version_reference(
            db,
            dataset_version_id=dataset_version_id,
            reference_kind="mount",
            reference_id=mount.id,
            referencing_study_id=study.id,
        )

    return mount


def record_dataset_version_reference(
    db: Session,
    *,
    dataset_version_id,
    reference_kind: str,
    reference_id,
    referencing_study_id: str | None,
) -> DatasetVersionReference:
    """Phase 4 (docs_v2/3-25) D: 登记一条版本引用追踪记录。

    幂等：同 (version_id, kind, reference_id) 不重复登记。
    """
    existing = (
        db.query(DatasetVersionReference)
        .filter(
            DatasetVersionReference.dataset_version_id == dataset_version_id,
            DatasetVersionReference.reference_kind == reference_kind,
            DatasetVersionReference.reference_id == reference_id,
        )
        .first()
    )
    if existing is not None:
        return existing
    ref = DatasetVersionReference(
        dataset_version_id=dataset_version_id,
        reference_kind=reference_kind,
        reference_id=reference_id,
        referencing_study_id=referencing_study_id,
    )
    db.add(ref)
    db.flush()
    return ref


def get_study_dataset_mount(
    db: Session,
    *,
    study: Study,
    mount_id: UUID,
) -> StudyDatasetMount | None:
    return (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.study_id == study.id, StudyDatasetMount.id == mount_id)
        .first()
    )


def get_study_dataset_mount_by_name(
    db: Session,
    *,
    study: Study,
    mount_name: str,
    active_only: bool = True,
) -> StudyDatasetMount | None:
    query = db.query(StudyDatasetMount).filter(
        StudyDatasetMount.study_id == study.id,
        StudyDatasetMount.mount_name == mount_name,
    )
    if active_only:
        query = query.filter(StudyDatasetMount.is_active.is_(True))
    return query.first()


def get_active_study_dataset_mount_for_asset(
    db: Session,
    *,
    study: Study,
    dataset_asset: DatasetAsset,
) -> StudyDatasetMount | None:
    return (
        db.query(StudyDatasetMount)
        .filter(
            StudyDatasetMount.study_id == study.id,
            StudyDatasetMount.dataset_asset_id == dataset_asset.id,
            StudyDatasetMount.is_active.is_(True),
        )
        .order_by(StudyDatasetMount.mounted_at.desc(), StudyDatasetMount.id.desc())
        .first()
    )


def update_study_dataset_mount(
    db: Session,
    *,
    study: Study,
    mount: StudyDatasetMount,
    mount_name: str | None = None,
    selection_json: dict[str, Any] | None = None,
    is_active: bool | None = None,
    dataset_version_id=None,
    actor=None,
) -> StudyDatasetMount:
    if mount_name is not None and mount_name != mount.mount_name:
        existing = (
            db.query(StudyDatasetMount)
            .filter(StudyDatasetMount.study_id == study.id, StudyDatasetMount.mount_name == mount_name)
            .first()
        )
        if existing is not None and existing.id != mount.id:
            raise DatasetAssetConflictError(f"Study dataset mount name already exists: {mount_name}")
        mount.mount_name = mount_name
    if selection_json is not None:
        mount.selection_json = selection_json
    if is_active is not None:
        mount.is_active = is_active
    # Phase 3 (docs_v2/3-25) C: 升级 mount 锁定的版本（同样走状态 + 可见性网关校验）
    if dataset_version_id is not None and dataset_version_id != mount.dataset_version_id:
        # 可见性网关用「当前操作者」校验，而非原始挂载人 mount.mounted_by——后者可能早已
        # 不在 dataset_members 授权名单里，升级版本时该用此刻发起者的授权。
        _ensure_version_mountable(
            db,
            dataset_asset=mount.dataset_asset,
            dataset_version_id=dataset_version_id,
            target_study_id=mount.study_id,
            actor=actor,
        )
        mount.dataset_version_id = dataset_version_id
        # Phase 4 (docs_v2/3-25) D: 升级到新版本时登记一条新引用（旧引用保留作历史）
        record_dataset_version_reference(
            db,
            dataset_version_id=dataset_version_id,
            reference_kind="mount",
            reference_id=mount.id,
            referencing_study_id=mount.study_id,
        )
    db.flush()
    return mount


def list_study_dataset_mounts(db: Session, *, study: Study) -> list[StudyDatasetMount]:
    return (
        db.query(StudyDatasetMount)
        .filter(StudyDatasetMount.study_id == study.id)
        .order_by(StudyDatasetMount.mounted_at.desc(), StudyDatasetMount.id.desc())
        .all()
    )
