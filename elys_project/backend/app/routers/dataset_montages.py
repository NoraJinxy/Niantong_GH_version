"""
Purpose: 自定义电极位置文件（montage）上传 / 列举 / 删除。数据集资产级，供 Pipeline「通道定位」节点选用。
Related: app/models/study.py(DatasetMontage), app/routers/dataset_assets.py,
         app/engine/preprocess/channel_location.py, app/pipeline/dispatcher.py（按 id 解析物理路径）, wiki 9-0x。
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import DatasetMontage, Study, StudyDatasetMount, User
from app.routers._dataset_shared import require_system_permission
from app.routers.auth import get_current_user
from app.services.dataset_assets import can_write_dataset_asset, get_dataset_asset_for_user
from app.services.study_access import require_study_read

settings = get_settings()

router = APIRouter(prefix="/api/v1", tags=["montages"])

# mne.channels.read_custom_montage 支持的电极位置文件扩展名（去点小写）
SUPPORTED_MONTAGE_EXTENSIONS = {
    "elc", "sfp", "bvef", "tsv", "csv", "txt", "loc", "locs", "eloc", "elp", "xyz", "csd",
}
# 电极文件都很小（几十个点），5MB 足够；超出多半是选错了文件，直接挡掉
MAX_MONTAGE_BYTES = 5 * 1024 * 1024


class MontageResponse(BaseModel):
    id: str
    dataset_asset_id: str
    name: str
    original_filename: str | None = None
    file_format: str
    n_electrodes: int | None = None
    file_size: int | None = None
    created_at: str | None = None


class MontageListResponse(BaseModel):
    montages: list[MontageResponse]


def _to_response(row: DatasetMontage) -> MontageResponse:
    return MontageResponse(
        id=str(row.id),
        dataset_asset_id=str(row.dataset_asset_id),
        name=row.name,
        original_filename=row.original_filename,
        file_format=row.file_format,
        n_electrodes=row.n_electrodes,
        file_size=row.file_size,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


def _montage_dir(dataset_asset_id: uuid.UUID | str) -> Path:
    return Path(settings.DATASETS_STORAGE_ROOT) / str(dataset_asset_id) / "montages"


@router.post(
    "/dataset-assets/{asset_id}/montages",
    response_model=MontageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_dataset_montage(
    asset_id: uuid.UUID,
    file: UploadFile = File(...),
    name: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有上传电极位置文件的权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if not can_write_dataset_asset(current_user, asset):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户没有写该 Dataset 资产的权限")

    raw_name = (file.filename or "montage").replace("\\", "/").split("/")[-1]
    raw_name = "".join(ch for ch in raw_name if ch.isprintable())[:128] or "montage"
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in SUPPORTED_MONTAGE_EXTENSIONS:
        supported = ", ".join("." + e for e in sorted(SUPPORTED_MONTAGE_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"不支持的电极文件类型 .{ext}；支持：{supported}",
        )
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="文件为空")
    if len(contents) > MAX_MONTAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="电极位置文件过大（>5MB），请确认是否选错文件",
        )

    montage_id = uuid.uuid4()
    target_dir = _montage_dir(asset.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{montage_id}.{ext}"
    target_path = target_dir / stored_name
    target_path.write_bytes(contents)

    # 用 MNE 试解析做校验：解析不了 = 不是有效电极文件，删盘 + 422（绝不留无效残骸）
    try:
        import mne  # noqa: PLC0415

        montage = mne.channels.read_custom_montage(str(target_path))
        n_electrodes = len(montage.ch_names)
        if n_electrodes < 3:
            raise ValueError("有效电极点少于 3 个，地形图无法插值")
    except Exception as exc:
        try:
            target_path.unlink()
        except OSError:
            pass
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"无法解析为电极位置文件：{exc}",
        )

    relative_path = f"montages/{stored_name}"
    row = DatasetMontage(
        id=montage_id,
        dataset_asset_id=asset.id,
        name=(name or "").strip() or raw_name,
        original_filename=raw_name,
        file_format=ext,
        storage_uri=f"elys://datasets/{asset.id}/{relative_path}",
        relative_path=relative_path,
        n_electrodes=n_electrodes,
        file_size=len(contents),
        sha256=hashlib.sha256(contents).hexdigest(),
        created_by=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)


@router.get("/dataset-assets/{asset_id}/montages", response_model=MontageListResponse)
def list_dataset_montages(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:read", "当前用户没有查看电极位置文件的权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    rows = (
        db.query(DatasetMontage)
        .filter(DatasetMontage.dataset_asset_id == asset.id)
        .order_by(DatasetMontage.created_at.desc())
        .all()
    )
    return MontageListResponse(montages=[_to_response(r) for r in rows])


@router.delete("/dataset-assets/{asset_id}/montages/{montage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset_montage(
    asset_id: uuid.UUID,
    montage_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_system_permission(current_user, "data:write", "当前用户没有删除电极位置文件的权限")
    asset = get_dataset_asset_for_user(db, asset_id=asset_id, user=current_user)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset 资产不存在或无权访问")
    if not can_write_dataset_asset(current_user, asset):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前用户没有写该 Dataset 资产的权限")
    row = (
        db.query(DatasetMontage)
        .filter(DatasetMontage.id == montage_id, DatasetMontage.dataset_asset_id == asset.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="电极位置文件不存在")
    path = Path(settings.DATASETS_STORAGE_ROOT) / str(asset.id) / row.relative_path
    db.delete(row)
    db.commit()
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
    return None


@router.get("/studies/{study_id}/montages", response_model=MontageListResponse)
def list_study_montages(
    study_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """研究项可见的全部自定义电极文件 = 该研究项挂载的所有数据集资产下的 montage。供「通道定位」节点选择器用。"""
    require_system_permission(current_user, "data:read", "当前用户没有查看电极位置文件的权限")
    require_study_read(db.query(Study).filter(Study.id == study_id).first(), db, current_user)
    asset_ids = [
        m.dataset_asset_id
        for m in db.query(StudyDatasetMount.dataset_asset_id)
        .filter(StudyDatasetMount.study_id == study_id, StudyDatasetMount.is_active.is_(True))
        .all()
    ]
    if not asset_ids:
        return MontageListResponse(montages=[])
    rows = (
        db.query(DatasetMontage)
        .filter(DatasetMontage.dataset_asset_id.in_(asset_ids))
        .order_by(DatasetMontage.created_at.desc())
        .all()
    )
    return MontageListResponse(montages=[_to_response(r) for r in rows])
