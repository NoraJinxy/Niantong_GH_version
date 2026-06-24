"""
Purpose: Define SQLAlchemy ORM models for the user database area.
Related: database/init.sql, app/schemas/*, app/routers/*, docs_v2/3-00.
"""

from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(128))
    institution = Column(String(256))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = relationship("Role", secondary="user_roles", back_populates="users")

    def has_permission(self, code: str) -> bool:
        for role in self.roles:
            for perm in role.permissions:
                if perm.code == code:
                    return True
        return False

    def has_role(self, code: str) -> bool:
        return any(r.code == code for r in self.roles)

    def to_dict(self):
        return {
            "id": str(self.id),
            "username": self.username,
            "full_name": self.full_name,
            "institution": self.institution,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "roles": [r.code for r in self.roles],
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
