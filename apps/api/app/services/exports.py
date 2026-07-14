"""Findings exports: CSV, JSON (audit), and a deterministic PDF evidence report.

The PDF is generated with fpdf2 from stored data only — no LLM involvement — and
always includes contradicting and missing evidence plus the disclaimer.
"""

import csv
import io
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Client,
    Finding,
    FindingEvidence,
    Project,
    ReviewDecision,
    ReviewRun,
)
from app.services.review.money import format_minor

DISCLAIMER = (
    "ScopeGuard provides operational review assistance. Findings are not legal advice "
    "and are not accounting advice. Human verification is required. Contract "
    "interpretation may be ambiguous. Potential value does not equal invoiced or "
    "collected revenue."
)


def findings_to_csv(db: Session, organization_id: uuid.UUID, findings: list[Finding]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "finding_id",
            "project",
            "finding_type",
            "title",
            "classification",
            "confidence",
            "potential_value",
            "currency",
            "review_status",
            "risk_level",
            "evidence_completeness",
            "created_at",
        ]
    )
    project_names = {
        p.id: p.name
        for p in db.execute(
            select(Project).where(Project.organization_id == organization_id)
        ).scalars()
    }
    for finding in findings:
        value = (
            f"{finding.potential_value_minor / 100:.2f}"
            if finding.potential_value_minor is not None
            else "unavailable"
        )
        writer.writerow(
            [
                str(finding.id),
                project_names.get(finding.project_id, ""),
                finding.finding_type.value,
                finding.title,
                finding.classification.value,
                finding.confidence,
                value,
                finding.currency or "",
                finding.review_status.value,
                finding.risk_level.value,
                finding.evidence_score,
                finding.created_at.isoformat(),
            ]
        )
    return output.getvalue()


def finding_to_audit_json(db: Session, finding: Finding) -> dict:
    evidence = list(
        db.execute(
            select(FindingEvidence).where(FindingEvidence.finding_id == finding.id)
        ).scalars()
    )
    decisions = list(
        db.execute(
            select(ReviewDecision)
            .where(ReviewDecision.finding_id == finding.id)
            .order_by(ReviewDecision.created_at)
        ).scalars()
    )
    run = db.get(ReviewRun, finding.review_run_id)
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "disclaimer": DISCLAIMER,
        "finding": {
            "id": str(finding.id),
            "type": finding.finding_type.value,
            "title": finding.title,
            "explanation": finding.explanation,
            "classification": finding.classification.value,
            "confidence": finding.confidence,
            "potential_value_minor": finding.potential_value_minor,
            "value_unavailable_reason": finding.value_unavailable_reason,
            "currency": finding.currency,
            "review_status": finding.review_status.value,
            "risk_level": finding.risk_level.value,
            "evidence_completeness": finding.evidence_score,
            "evidence_score_breakdown": finding.evidence_score_breakdown,
            "calculation_breakdown": finding.calculation_breakdown,
            "missing_evidence": finding.missing_evidence,
            "contradicting_summary": finding.contradicting_summary,
            "created_at": finding.created_at.isoformat(),
        },
        "review_run": {
            "id": str(run.id) if run else None,
            "model_name": run.model_name if run else None,
            "prompt_version": run.prompt_version if run else None,
            "billing_period_start": str(run.billing_period_start) if run else None,
            "billing_period_end": str(run.billing_period_end) if run else None,
        },
        "evidence": [
            {
                "evidence_type": e.evidence_type,
                "entity_type": e.entity_type.value,
                "entity_id": str(e.entity_id) if e.entity_id else None,
                "quotation": e.quotation,
                "document_page": e.document_page,
                "section_reference": e.section_reference,
                "relevance_explanation": e.relevance_explanation,
            }
            for e in evidence
        ],
        "decisions": [
            {
                "previous_status": d.previous_status.value,
                "new_status": d.new_status.value,
                "reason": d.reason,
                "reviewer_id": str(d.reviewer_id) if d.reviewer_id else None,
                "created_at": d.created_at.isoformat(),
            }
            for d in decisions
        ],
    }


def _pdf_safe(text: str, max_token: int = 60) -> str:
    """Make text safe for fpdf2 core fonts (latin-1) and line-breakable.

    Long unbroken tokens (hashes, JSON blobs) overflow a cell's width and raise
    'Not enough horizontal space'; insert spaces so every token can wrap.
    """
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    # Insert a break opportunity after any run of `max_token` non-whitespace chars.
    out: list[str] = []
    run = 0
    for char in text:
        if char.isspace():
            run = 0
            out.append(char)
            continue
        if run >= max_token:
            out.append(" ")
            run = 0
        out.append(char)
        run += 1
    return "".join(out)


def finding_to_pdf(db: Session, finding: Finding) -> bytes:
    from fpdf import FPDF

    data = finding_to_audit_json(db, finding)
    project = db.get(Project, finding.project_id)
    client = db.get(Client, project.client_id) if project else None

    pdf = FPDF()
    pdf.set_margins(left=15, top=15, right=15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    def heading(text: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 30, 30)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 7, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def body(text: str, size: int = 10) -> None:
        pdf.set_font("Helvetica", "", size)
        pdf.set_text_color(50, 50, 50)
        pdf.set_x(pdf.l_margin)
        pdf.multi_cell(0, 5.5, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 9, "ScopeGuard Evidence Report", new_x="LMARGIN", new_y="NEXT")
    body(
        f"Generated: {data['exported_at']}   Finding: {finding.id}\n"
        f"Client: {client.display_name if client else '-'}   "
        f"Project: {project.name if project else '-'}\n"
        f"Billing period: {data['review_run']['billing_period_start']} to "
        f"{data['review_run']['billing_period_end']}   "
        f"Model: {data['review_run']['model_name']} "
        f"(prompt {data['review_run']['prompt_version']})",
        size=9,
    )
    pdf.ln(2)

    heading("Finding")
    body(
        f"{finding.title}\n\nType: {finding.finding_type.value}   "
        f"Classification: {finding.classification.value}   "
        f"Confidence: {finding.confidence}   Risk: {finding.risk_level.value}   "
        f"Status: {finding.review_status.value}"
    )
    body(finding.explanation)

    heading("Potential value")
    if finding.potential_value_minor is not None:
        body(
            f"{format_minor(finding.potential_value_minor, finding.currency or 'USD')} "
            "(potential value identified - NOT approved, invoiced, or collected revenue)"
        )
    else:
        body(f"Value unavailable: {finding.value_unavailable_reason}")

    heading("Calculation")
    body(json.dumps(finding.calculation_breakdown, indent=1, default=str)[:4000], size=8)

    heading("Evidence completeness")
    body(json.dumps(finding.evidence_score_breakdown, indent=1, default=str)[:2500], size=8)

    heading("Evidence (supporting and contradicting)")
    for item in data["evidence"]:
        marker = "SUPPORTING" if item["evidence_type"] == "supporting" else "CONTRADICTING"
        location = ""
        if item["document_page"]:
            location += f" p.{item['document_page']}"
        if item["section_reference"]:
            location += f" §{item['section_reference']}"
        body(
            f"[{marker}] {item['entity_type']}{location}\n"
            + (f'Quote: "{item["quotation"]}"\n' if item["quotation"] else "")
            + (item["relevance_explanation"] or ""),
            size=9,
        )
    if finding.contradicting_summary:
        body(f"Contradicting summary: {finding.contradicting_summary}", size=9)
    if finding.missing_evidence:
        heading("Missing evidence")
        for missing in finding.missing_evidence:
            body(f"- {missing}", size=9)

    heading("Review history")
    if data["decisions"]:
        for decision in data["decisions"]:
            body(
                f"{decision['created_at']}: {decision['previous_status']} -> "
                f"{decision['new_status']} - {decision['reason']}",
                size=9,
            )
    else:
        body("No human decisions recorded yet.", size=9)

    heading("Disclaimer")
    body(DISCLAIMER, size=9)

    return bytes(pdf.output())
