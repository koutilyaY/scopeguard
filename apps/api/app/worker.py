"""Celery application and background tasks.

Tasks are idempotent: extraction re-runs replace prior state; review runs check
status before executing. Failures mark user-visible states while full tracebacks
stay in server logs only.
"""

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger("scopeguard.worker")

settings = get_settings()
celery_app = Celery(
    "scopeguard",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_retry_delay=10,
    broker_connection_retry_on_startup=True,
    # failed tasks land in a failed state visible via result backend; no silent loss
    task_track_started=True,
)


def _session():
    from app.db import get_sessionmaker

    return get_sessionmaker()()


@celery_app.task(bind=True, max_retries=3, retry_backoff=True, retry_backoff_max=120)
def extract_document_task(self, document_id: str) -> dict:
    """Extract text from an uploaded document and store status + text."""
    from app.models import Document
    from app.models.enums import ExtractionStatus
    from app.services.extraction import UNREADABLE_MESSAGE, extract_document
    from app.services.files import get_extension
    from app.services.storage import get_object

    db = _session()
    try:
        document = db.get(Document, document_id)
        if document is None:
            return {"status": "missing"}
        document.extraction_status = ExtractionStatus.processing
        db.commit()
        try:
            data = get_object(document.storage_key)
        except Exception as exc:
            document.extraction_status = ExtractionStatus.failed
            document.extraction_error = "Stored file could not be read."
            db.commit()
            logger.exception("Storage read failed for document %s", document_id)
            raise self.retry(exc=exc) from exc

        extension = get_extension(document.original_filename)
        result = extract_document(extension, data)
        if result.ok:
            document.extraction_status = ExtractionStatus.completed
            document.extracted_text = result.full_text
            document.extraction_error = None
        elif result.error == UNREADABLE_MESSAGE:
            document.extraction_status = ExtractionStatus.unreadable
            document.extraction_error = UNREADABLE_MESSAGE
        else:
            document.extraction_status = ExtractionStatus.failed
            document.extraction_error = (
                "Text extraction failed. The file may be corrupted or unsupported."
            )
            logger.error("Extraction failed for %s: %s", document_id, result.error)
        db.commit()
        return {"status": document.extraction_status.value}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=2, retry_backoff=True, retry_backoff_max=300)
def extract_contract_clauses_task(self, contract_id: str) -> dict:
    """LLM clause extraction for a contract's governing document."""
    import uuid as _uuid

    from app.services.contract_extraction import extract_clauses_for_contract
    from app.services.llm import LLMUnavailableError

    db = _session()
    try:
        try:
            return extract_clauses_for_contract(db, _uuid.UUID(contract_id))
        except LLMUnavailableError as exc:
            logger.warning("LLM unavailable for contract extraction, retrying: %s", exc)
            raise self.retry(exc=exc) from exc
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=1)
def execute_review_run_task(self, review_run_id: str) -> dict:
    from app.models import ReviewRun
    from app.models.enums import ReviewRunStatus
    from app.services.review.engine import execute_review_run

    db = _session()
    try:
        run = db.get(ReviewRun, review_run_id)
        if run is None:
            return {"status": "missing"}
        if run.status not in (ReviewRunStatus.pending,):
            # idempotency: never re-execute a running/finished run
            return {"status": run.status.value, "note": "already processed"}
        execute_review_run(db, run.id)
        db.refresh(run)
        return {"status": run.status.value}
    finally:
        db.close()
