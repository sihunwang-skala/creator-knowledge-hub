# Architecture & trade-offs

```mermaid
flowchart LR
  UI[React + Tailwind SPA] -->|REST /api| API[FastAPI]
  API --> POL{Source Permission Policy}
  POL -- approved --> AN[Analysis pipeline]
  POL -- pending/denied --> BLOCK[Blocked: Source Required]
  AN --> LLM[LLM provider interface<br/>local-extractive | anthropic]
  AN --> DB[(SQLite / Postgres)]
  API --> YT[YouTube Data API v3<br/>official only]
  API --> SRCH[Search provider<br/>fixture | brave]
  JOBS[Job queue + scheduler] --> YT
  JOBS --> DB
  API --> FTS[(FTS5 index)]
```

| Choice | Why | Alternative / trade-off |
|---|---|---|
| FastAPI + SQLAlchemy 2 + Pydantic | typed API, easy tests, SQLite→Postgres by URL | Django: heavier for this API-only shape |
| SQLite + FTS5 for MVP | zero setup, good full-text | single writer; Postgres FTS needed at scale |
| DB-backed job queue | no extra infra, restart-safe, idempotent | Celery/RQ/Redis scale better, more ops |
| Local extractive summarizer default | works with no keys/cost; testable | Not a real LLM — quality is limited. Anthropic adapter is optional |
| Heuristic claim judge | transparent and testable offline | Weaker than LLM/retrieval judges; labelled as heuristic |
| No vector DB / multi-agent / LangGraph | not needed for FTS-first MVP | Semantic search is a roadmap item |
| Vite SPA, hash routing | simple static hosting by FastAPI | Next.js SSR unnecessary for a private app |

## Data model (key tables)
`users` · `channels` · `subscriptions` · `videos` · `user_videos` (state/analysis_status) · `sources` (permission + provenance) · `notes` (+ `note_revisions`) · `claims` (+ `evidence`) · `syntheses` · `digests` · `knowledge_changes` · `jobs` · `quota_usage` · `llm_usage` · `creator_optins` · `takedown_requests`.

## Public vs private boundary
This repository is the **public demo**: runnable code, synthetic samples, tests. Keep **out** of it: API keys, real user libraries, any third-party transcript, business plans/contracts, and any ranking/verification algorithms you decide to keep proprietary (the heuristics here are deliberately simple). Publishing code is not trade-secret protection; anyone can read and copy it. A future private "pro" package should plug in via the existing interfaces (`LLMProvider`, `SearchProvider`, `YouTubeProvider`, source connectors) rather than forking this repo.
