"""WorkItem, TimeEntry, CustomerRequest — imported operational evidence."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AuthorizationStatus, BillableStatus, WorkItemStatus


class WorkItem(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "external_system", "external_id", name="uq_work_items_external"
        ),
        Index("ix_work_items_org_project", "organization_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    external_system: Mapped[str] = mapped_column(String(50), nullable=False, default="jira_csv")
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkItemStatus] = mapped_column(
        Enum(WorkItemStatus, native_enum=False, length=20), nullable=False
    )
    work_type: Mapped[str | None] = mapped_column(String(50))
    assignee: Mapped[str | None] = mapped_column(String(255))
    created_at_external: Mapped[datetime | None] = mapped_column()
    completed_at_external: Mapped[datetime | None] = mapped_column()
    source_url: Mapped[str | None] = mapped_column(String(500))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class TimeEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "time_entries"
    __table_args__ = (
        CheckConstraint("minutes > 0", name="ck_time_entries_positive_minutes"),
        Index("ix_time_entries_org_project_date", "organization_id", "project_id", "work_date"),
        # exact-duplicate detection key
        Index("ix_time_entries_org_hash", "organization_id", "content_hash"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    work_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="SET NULL"), index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(100))
    employee_name: Mapped[str] = mapped_column(String(255), nullable=False)
    employee_role: Mapped[str | None] = mapped_column(String(100))
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    billable_status: Mapped[BillableStatus] = mapped_column(
        Enum(BillableStatus, native_enum=False, length=20),
        nullable=False,
        default=BillableStatus.unknown,
    )
    description: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="csv_import")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class CustomerRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin, OrgScopedMixin):
    __tablename__ = "customer_requests"
    __table_args__ = (Index("ix_customer_requests_org_project", "organization_id", "project_id"),)

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE")
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sender: Mapped[str | None] = mapped_column(String(320))
    recipients: Mapped[str | None] = mapped_column(Text)
    request_date: Mapped[date | None] = mapped_column(Date)
    body: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    linked_work_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="SET NULL")
    )
    customer_authorization_status: Mapped[AuthorizationStatus] = mapped_column(
        Enum(AuthorizationStatus, native_enum=False, length=20),
        nullable=False,
        default=AuthorizationStatus.none,
    )
