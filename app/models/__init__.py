"""All ORM models – importing this package registers every table with Base."""

from app.models.base import Base
from app.models.enums import Role, role_at_least
from app.models.user import User
from app.models.homework import Homework
from app.models.attachment import Attachment
from app.models.point_transaction import PointTransaction
from app.models.setting import Setting
from app.models.audit_log import AuditLog
from app.models.auth_code import AuthCode
from app.models.api_key import ApiKey

__all__ = [
    "Base",
    "Role",
    "role_at_least",
    "User",
    "Homework",
    "Attachment",
    "PointTransaction",
    "Setting",
    "AuditLog",
    "AuthCode",
    "ApiKey",
]
