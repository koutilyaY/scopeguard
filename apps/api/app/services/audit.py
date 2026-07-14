"""Audit trail helper. Every state-changing operation must record an event."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.logging import redact, request_id_var
from app.models import AuditEvent


def record_audit_event(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditEvent:
    """Add an audit event to the current transaction (caller commits)."""
    event = AuditEvent(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=redact(before_state) if before_state else None,
        after_state=redact(after_state) if after_state else None,
        ip_address=ip_address,
        request_id=request_id_var.get(),
        created_at=datetime.now(UTC),
    )
    db.add(event)
    return event
