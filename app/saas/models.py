from dataclasses import dataclass
from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class CreditBucket(StrEnum):
    FREE = "free"
    PAID = "paid"


class EntitlementSource(StrEnum):
    FREE_CREDIT = "free_credit"
    PAID_CREDIT = "paid_credit"
    ADMIN_GRANT = "admin_grant"


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: int
    email: str
    role: UserRole

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
