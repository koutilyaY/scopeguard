# ADR-0001: Local Ollama instead of paid AI APIs

## Status
Accepted

## Context
ScopeGuard must run entirely on free, local, open-source components with no paid API,
no SaaS, and no credit card. It also processes sensitive customer contracts.

## Decision
Use [Ollama](https://ollama.com) as the default LLM provider for both chat and
embeddings, behind a provider interface (`generate_structured`, `create_embeddings`,
`health_check`, `model_metadata`). Models are configurable via `OLLAMA_CHAT_MODEL` /
`OLLAMA_EMBED_MODEL`. A deterministic `FakeLLMProvider` implements the same interface
for tests and offline evaluation.

## Consequences
- No external data egress by default; contracts stay on the local machine.
- Model quality varies by hardware and chosen model — mitigated by keeping all
  monetary and duplicate logic deterministic and requiring human review.
- Tests never depend on a live model. CI runs against the fake provider.
- A startup check (`/health/ollama`) reports missing models and exact `ollama pull`
  commands.
