"""FastAPI dependencies: current user, RBAC, organization scoping."""

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.logging import org_id_var, user_id_var
from app.models import AuthSession, User
from app.models.enums import UserRole
from app.security.sessions import resolve_session

# Role hierarchy: any role listed later includes the permissions of roles before it.
ROLE_ORDER = [
    UserRole.read_only,
    UserRole.reviewer,
    UserRole.project_manager,
    UserRole.finance_manager,
    UserRole.organization_admin,
]

# Roles allowed to make review decisions
DECISION_ROLES = {
    UserRole.reviewer,
    UserRole.project_manager,
    UserRole.finance_manager,
    UserRole.organization_admin,
}
# Roles allowed to import data / upload documents
WRITE_ROLES = {
    UserRole.project_manager,
    UserRole.finance_manager,
    UserRole.organization_admin,
}


@dataclass
class AuthContext:
    user: User
    session: AuthSession

    @property
    def organization_id(self) -> uuid.UUID:
        return self.user.organization_id


def get_auth_context(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    resolved = resolve_session(db, token)
    if resolved is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session expired or invalid")
    session, user = resolved
    user_id_var.set(str(user.id))
    org_id_var.set(str(user.organization_id))
    return AuthContext(user=user, session=session)


def require_role(minimum: UserRole):
    """Dependency factory enforcing a minimum role in the hierarchy."""

    def checker(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ROLE_ORDER.index(ctx.user.role) < ROLE_ORDER.index(minimum):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Requires role {minimum.value} or higher",
            )
        return ctx

    return checker


def require_any_role(allowed: set[UserRole]):
    def checker(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if ctx.user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return ctx

    return checker


def get_org_object(db: Session, model, object_id: uuid.UUID, organization_id: uuid.UUID):
    """Fetch an org-owned row, returning 404 when absent OR owned by another tenant.

    Returning 404 (not 403) for cross-tenant IDs avoids confirming that the object exists.
    """
    obj = db.get(model, object_id)
    if obj is None or obj.organization_id != organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return obj
