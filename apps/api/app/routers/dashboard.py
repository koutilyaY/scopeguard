"""Dashboard aggregates. Potential value is always separated from approved and
invoiced value — never presented as recovered revenue."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import AuthContext, get_auth_context
from app.models import (
    Allowance,
    Client,
    Finding,
    Invoice,
    Project,
    ReviewRun,
    TimeEntry,
    WorkItem,
)
from app.models.enums import FindingType, InvoiceStatus, ReviewStatus

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class ValueByCurrency(BaseModel):
    currency: str
    amount_minor: int


class AllowanceHealth(BaseModel):
    allowance_id: uuid.UUID
    contract_id: uuid.UUID
    allowance_type: str
    included_minutes: int
    consumed_minutes_this_period: int
    remaining_minutes: int
    period_label: str


class DashboardOut(BaseModel):
    pending_review_count: int
    # Stage-separated values (per currency; currencies are never combined)
    potential_value: list[ValueByCurrency]
    approved_for_billing_value: list[ValueByCurrency]
    invoiced_value: list[ValueByCurrency]
    rejected_value: list[ValueByCurrency]
    findings_by_type: dict[str, int]
    findings_by_client: dict[str, int]
    findings_by_project: dict[str, int]
    recent_review_runs: list[dict]
    allowances_nearing_exhaustion: list[AllowanceHealth]
    value_disclaimer: str = (
        "Potential value is unreviewed and does not represent recoverable or recovered revenue."
    )


def _sum_by_currency(rows: list[tuple[str | None, int | None]]) -> list[ValueByCurrency]:
    totals: dict[str, int] = {}
    for currency, amount in rows:
        if currency is None or amount is None:
            continue
        totals[currency] = totals.get(currency, 0) + amount
    return [ValueByCurrency(currency=c, amount_minor=a) for c, a in sorted(totals.items())]


@router.get("", response_model=DashboardOut)
def dashboard(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> DashboardOut:
    org_id = ctx.organization_id

    pending = db.execute(
        select(func.count())
        .select_from(Finding)
        .where(
            Finding.organization_id == org_id,
            Finding.review_status.in_([ReviewStatus.pending, ReviewStatus.needs_more_evidence]),
        )
    ).scalar_one()

    def value_rows(statuses: list[ReviewStatus]) -> list[tuple[str | None, int | None]]:
        return [
            (row[0], row[1])
            for row in db.execute(
                select(Finding.currency, func.sum(Finding.potential_value_minor))
                .where(
                    Finding.organization_id == org_id,
                    Finding.review_status.in_(statuses),
                    Finding.potential_value_minor.isnot(None),
                )
                .group_by(Finding.currency)
            ).all()
        ]

    invoiced_rows = [
        (row[0], row[1])
        for row in db.execute(
            select(Invoice.currency, func.sum(Invoice.total_minor))
            .where(
                Invoice.organization_id == org_id,
                Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.paid]),
            )
            .group_by(Invoice.currency)
        ).all()
    ]

    by_type = {finding_type.value: 0 for finding_type in FindingType}
    for finding_type, count in db.execute(
        select(Finding.finding_type, func.count())
        .where(Finding.organization_id == org_id)
        .group_by(Finding.finding_type)
    ).all():
        by_type[finding_type.value] = count
    by_type = {k: v for k, v in by_type.items() if v}

    by_client = {
        name: count
        for name, count in db.execute(
            select(Client.display_name, func.count(Finding.id))
            .join(Project, Project.client_id == Client.id)
            .join(Finding, Finding.project_id == Project.id)
            .where(Finding.organization_id == org_id)
            .group_by(Client.display_name)
        ).all()
    }
    by_project = {
        name: count
        for name, count in db.execute(
            select(Project.name, func.count(Finding.id))
            .join(Finding, Finding.project_id == Project.id)
            .where(Finding.organization_id == org_id)
            .group_by(Project.name)
        ).all()
    }

    recent_runs = [
        {
            "id": str(run.id),
            "project_id": str(run.project_id),
            "status": run.status.value,
            "billing_period_start": str(run.billing_period_start),
            "billing_period_end": str(run.billing_period_end),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "findings": (run.stats or {}).get("findings_created"),
        }
        for run in db.execute(
            select(ReviewRun)
            .where(ReviewRun.organization_id == org_id)
            .order_by(ReviewRun.created_at.desc())
            .limit(8)
        ).scalars()
    ]

    # allowance health for the current month
    from app.services.review.allowances import period_bounds_for

    allowance_health: list[AllowanceHealth] = []
    today = date.today()
    for allowance in db.execute(
        select(Allowance).where(Allowance.organization_id == org_id)
    ).scalars():
        start, end, label = period_bounds_for(allowance, today)
        support_items = {
            w.id
            for w in db.execute(
                select(WorkItem).where(WorkItem.organization_id == org_id)
            ).scalars()
            if "support" in (w.work_type or "").lower()
        }
        consumed = 0
        for entry in db.execute(
            select(TimeEntry).where(
                TimeEntry.organization_id == org_id,
                TimeEntry.work_date >= start,
                TimeEntry.work_date < end,
            )
        ).scalars():
            if (entry.work_item_id in support_items) or (
                "support" in (entry.description or "").lower()
            ):
                consumed += entry.minutes
        remaining = max(0, allowance.included_quantity - consumed)
        if allowance.included_quantity and remaining <= allowance.included_quantity * 0.25:
            allowance_health.append(
                AllowanceHealth(
                    allowance_id=allowance.id,
                    contract_id=allowance.contract_id,
                    allowance_type=allowance.allowance_type.value,
                    included_minutes=allowance.included_quantity,
                    consumed_minutes_this_period=consumed,
                    remaining_minutes=remaining,
                    period_label=label,
                )
            )

    return DashboardOut(
        pending_review_count=pending,
        potential_value=_sum_by_currency(
            value_rows(
                [
                    ReviewStatus.pending,
                    ReviewStatus.needs_more_evidence,
                    ReviewStatus.approved_for_followup,
                ]
            )
        ),
        approved_for_billing_value=_sum_by_currency(
            value_rows([ReviewStatus.approved_for_billing])
        ),
        invoiced_value=_sum_by_currency(invoiced_rows),
        rejected_value=_sum_by_currency(value_rows([ReviewStatus.rejected])),
        findings_by_type=by_type,
        findings_by_client=by_client,
        findings_by_project=by_project,
        recent_review_runs=recent_runs,
        allowances_nearing_exhaustion=allowance_health,
    )
