"""
Purpose: Provide reusable service-layer logic for study_access so routers stay thin.
Related: app/routers/*, app/models/*, docs_v2/7-30.
"""

from enum import Enum

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Study, StudyMember, User


class StudyAccess(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    EXPORT = "export"
    RUN = "run"


def get_study_membership(db: Session, study: Study, user: User) -> StudyMember | None:
    return (
        db.query(StudyMember)
        .filter(StudyMember.study_id == study.id, StudyMember.user_id == user.id)
        .first()
    )


def require_study_access(
    study: Study | None,
    db: Session,
    user: User,
    access: StudyAccess,
) -> Study:
    if study is None or study.status == "deleted":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究项不存在")
    if study.status == "trashed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="研究项已在垃圾箱中，请先恢复研究项")

    if user.has_role("admin") or study.owner_id == user.id:
        return study

    membership = get_study_membership(db, study, user)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该研究项")

    allowed = {
        StudyAccess.READ: membership.can_read,
        StudyAccess.WRITE: membership.can_write or membership.role == "owner",
        StudyAccess.DELETE: membership.can_delete or membership.role == "owner",
        StudyAccess.EXPORT: membership.can_export or membership.role == "owner",
        StudyAccess.RUN: membership.can_run or membership.role == "owner",
    }[access]
    if allowed:
        return study

    messages = {
        StudyAccess.READ: "无权访问该研究项",
        StudyAccess.WRITE: "无权修改该研究项",
        StudyAccess.DELETE: "无权删除该研究项",
        StudyAccess.EXPORT: "无权导出该研究项",
        StudyAccess.RUN: "无权运行该研究项工作流",
    }
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=messages[access])


def require_study_read(study: Study | None, db: Session, user: User) -> Study:
    return require_study_access(study, db, user, StudyAccess.READ)


def require_study_write(study: Study | None, db: Session, user: User) -> Study:
    return require_study_access(study, db, user, StudyAccess.WRITE)


def require_study_run(study: Study | None, db: Session, user: User) -> Study:
    return require_study_access(study, db, user, StudyAccess.RUN)
