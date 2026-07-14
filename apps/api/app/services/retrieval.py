"""Structure-aware chunking and tenant-scoped pgvector retrieval."""

import re
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import ClauseEmbedding, Contract, ContractClause
from app.services.llm import get_llm_provider

SIMILARITY_THRESHOLD = 0.25  # cosine similarity floor
DEFAULT_TOP_K = 8
MAX_CHUNK_CHARS = 1600


@dataclass
class Chunk:
    text: str
    page_number: int | None
    section_reference: str | None
    index: int


def chunk_document_text(text: str) -> list[Chunk]:
    """Split extracted text on page markers, headings and paragraphs, keeping
    chunks under MAX_CHUNK_CHARS with their page/section metadata."""
    chunks: list[Chunk] = []
    current_page: int | None = None
    current_section: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            body = "\n".join(buffer).strip()
            if body:
                chunks.append(
                    Chunk(
                        text=body,
                        page_number=current_page,
                        section_reference=current_section,
                        index=len(chunks),
                    )
                )
            buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        page_match = re.match(r"^\[page (\d+)\]$", line.strip())
        if page_match:
            flush()
            current_page = int(page_match.group(1))
            continue
        heading = re.match(r"^(?:##\s*)?(\d+(?:\.\d+)*)[.\s]+\S", line.strip())
        if heading and len(line.strip()) < 90:
            flush()
            current_section = heading.group(1)
        if not line.strip():
            if sum(len(b) for b in buffer) > MAX_CHUNK_CHARS // 2:
                flush()
            continue
        buffer.append(line)
        if sum(len(b) for b in buffer) > MAX_CHUNK_CHARS:
            flush()
    flush()
    return chunks


def embed_clauses(db: Session, clauses: list[ContractClause]) -> int:
    """Create embeddings for verified-candidate clauses. Returns count stored."""
    if not clauses:
        return 0
    provider = get_llm_provider()
    texts = [f"{c.title}\n{c.source_text}" for c in clauses]
    vectors = provider.create_embeddings(texts)
    model_name = provider.model_metadata().embed_model
    for clause, vector in zip(clauses, vectors, strict=True):
        db.add(
            ClauseEmbedding(
                organization_id=clause.organization_id,
                clause_id=clause.id,
                chunk_index=0,
                chunk_text=clause.source_text,
                page_number=clause.page_number,
                section_reference=clause.section_reference,
                embedding_model=model_name,
                embedding=vector,
            )
        )
    return len(clauses)


@dataclass
class RetrievedClause:
    clause: ContractClause
    similarity: float


def retrieve_relevant_clauses(
    db: Session,
    *,
    organization_id: uuid.UUID,
    contract_ids: list[uuid.UUID],
    query_text: str,
    on_date: date | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> list[RetrievedClause]:
    """Vector retrieval strictly filtered to the organization and given contracts.

    Tenant and contract filters are applied in SQL *before* similarity ordering, so
    cross-tenant vectors can never be returned. Falls back to lexical retrieval when
    no embeddings exist (e.g. embeddings still being generated).
    """
    if not contract_ids:
        return []
    query_vector = get_llm_provider().create_embeddings([query_text])[0]

    distance = ClauseEmbedding.embedding.cosine_distance(query_vector)
    stmt = (
        select(ContractClause, distance.label("distance"))
        .join(ClauseEmbedding, ClauseEmbedding.clause_id == ContractClause.id)
        .where(
            ClauseEmbedding.organization_id == organization_id,
            ContractClause.organization_id == organization_id,
            ContractClause.contract_id.in_(contract_ids),
            ContractClause.rejected.is_(False),
            ContractClause.superseded_by_clause_id.is_(None),
        )
        .order_by(distance)
        .limit(top_k * 2)
    )
    if on_date is not None:
        stmt = stmt.where(
            or_(ContractClause.effective_from.is_(None), ContractClause.effective_from <= on_date),
            or_(ContractClause.effective_to.is_(None), ContractClause.effective_to >= on_date),
        )

    rows = db.execute(stmt).all()
    results: list[RetrievedClause] = []
    seen: set[uuid.UUID] = set()
    for clause, dist in rows:
        if clause.id in seen:
            continue
        seen.add(clause.id)
        similarity = 1.0 - float(dist)
        if similarity >= SIMILARITY_THRESHOLD:
            results.append(RetrievedClause(clause=clause, similarity=similarity))
        if len(results) >= top_k:
            break

    if results:
        return results

    # Lexical fallback: token overlap on clause text (hybrid retrieval safety net)
    clause_rows = (
        db.execute(
            select(ContractClause).where(
                ContractClause.organization_id == organization_id,
                ContractClause.contract_id.in_(contract_ids),
                ContractClause.rejected.is_(False),
                ContractClause.superseded_by_clause_id.is_(None),
            )
        )
        .scalars()
        .all()
    )
    query_tokens = {t for t in re.findall(r"[a-z0-9\-]+", query_text.lower()) if len(t) > 2}
    scored = []
    for clause in clause_rows:
        clause_tokens = {
            t for t in re.findall(r"[a-z0-9\-]+", clause.source_text.lower()) if len(t) > 2
        }
        overlap = len(query_tokens & clause_tokens)
        if overlap > 0:
            scored.append(RetrievedClause(clause=clause, similarity=overlap / 100.0))
    scored.sort(key=lambda r: r.similarity, reverse=True)
    return scored[:top_k]


def resolve_contract_ids_for_project(
    db: Session, organization_id: uuid.UUID, project_id: uuid.UUID, client_id: uuid.UUID
) -> list[uuid.UUID]:
    """Contracts scoped to the project, plus client-wide contracts (no project)."""
    rows = (
        db.execute(
            select(Contract.id).where(
                Contract.organization_id == organization_id,
                Contract.client_id == client_id,
                or_(Contract.project_id == project_id, Contract.project_id.is_(None)),
            )
        )
        .scalars()
        .all()
    )
    return list(rows)
