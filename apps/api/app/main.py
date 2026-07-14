"""ScopeGuard API entrypoint."""

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.logging import org_id_var, request_id_var, setup_logging, user_id_var
from app.routers import (
    allowances,
    artifacts,
    audit_events,
    auth,
    clauses,
    clients,
    contracts,
    customer_requests,
    dashboard,
    decisions,
    documents,
    findings,
    health,
    imports,
    invoices,
    organizations,
    projects,
    rates,
    reports,
    review_runs,
    time_entries,
    users,
    work_items,
)
from app.security.sessions import resolve_session

logger = logging.getLogger("scopeguard")

# Mutating methods require the CSRF double-submit header.
CSRF_EXEMPT_PATHS = {"/api/v1/auth/login"}
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title="ScopeGuard API",
        version="0.1.0",
        description=(
            "Evidence-backed scope and billing review. Findings are operational review "
            "assistance, not legal or accounting advice; human verification is required."
        ),
        docs_url="/docs" if not settings.is_production else None,
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request_id_var.set(request_id)
        user_id_var.set(None)
        org_id_var.set(None)

        # Request body size limit (defense in depth; uploads have their own limit)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_upload_bytes * 2:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request too large"},
            )

        # CSRF: double-submit check for mutating requests with a session cookie
        if (
            request.method not in SAFE_METHODS
            and request.url.path not in CSRF_EXEMPT_PATHS
            and request.cookies.get(settings.session_cookie_name)
        ):
            header_token = request.headers.get("X-CSRF-Token")
            if not header_token or not _csrf_valid(request, header_token):
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "CSRF token missing or invalid"},
                )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    def _csrf_valid(request: Request, header_token: str) -> bool:
        from app.db import get_sessionmaker

        token = request.cookies.get(settings.session_cookie_name)
        if not token:
            return False
        db = get_sessionmaker()()
        try:
            resolved = resolve_session(db, token)
            if resolved is None:
                return False
            session, _ = resolved
            import hmac

            return hmac.compare_digest(session.csrf_token, header_token)
        finally:
            db.close()

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": request_id_var.get(),
            },
        )

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(users.router, prefix=prefix)
    app.include_router(organizations.router, prefix=prefix)
    app.include_router(clients.router, prefix=prefix)
    app.include_router(projects.router, prefix=prefix)
    app.include_router(documents.router, prefix=prefix)
    app.include_router(contracts.router, prefix=prefix)
    app.include_router(clauses.router, prefix=prefix)
    app.include_router(rates.router, prefix=prefix)
    app.include_router(allowances.router, prefix=prefix)
    app.include_router(work_items.router, prefix=prefix)
    app.include_router(time_entries.router, prefix=prefix)
    app.include_router(customer_requests.router, prefix=prefix)
    app.include_router(invoices.router, prefix=prefix)
    app.include_router(imports.router, prefix=prefix)
    app.include_router(review_runs.router, prefix=prefix)
    app.include_router(findings.router, prefix=prefix)
    app.include_router(decisions.router, prefix=prefix)
    app.include_router(artifacts.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)
    app.include_router(audit_events.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)
    return app


app = create_app()
