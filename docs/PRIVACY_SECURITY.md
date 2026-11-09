# Privacy & security

| Control | Implementation | Test |
|---|---|---|
| Secrets via env | `CKH_*` variables (`config.py`), `.env` git-ignored, `.env.example` only | `scripts/secret_scan.py`, CI |
| Secret scanning | Regex scan of tracked files (Google/Anthropic/GitHub keys, private keys, tokens) | `scripts/secret_scan.py` in CI |
| Auth / access control | Opaque bearer token (SHA-256 hashed at rest); every query filtered by `user_id`; 404 for others' objects | `test_users_cannot_see_each_others_data` |
| Upload validation | `.txt/.srt/.vtt` only, UTF-8, no NUL, size cap (1 MB), names sanitised, **never written to disk** (path traversal moot) | `test_upload_validation`, `test_path_traversal_filename_neutralised` |
| SSRF | https only, no creds/ports, DNS answers must all be public, every redirect re-validated, size/type caps | `test_ssrf_*`, `test_safe_fetch_*` |
| Prompt injection | All external text is untrusted: control chars stripped, delimiter spoofing removed, instruction-like phrases flagged, text wrapped in `<untrusted_source>` with a "data, never instructions" system rule; model has no tools; output validated against a schema and citation rules | `test_injection_*`, `test_anthropic_provider_*` |
| Rate limiting | Per-user sliding window (120/min; 20/min for costly routes), per-IP for signup/takedown. **In-memory, single process** — use a shared store when scaling | `test_rate_limit_*` |
| Cost limits | Daily LLM call cap per user, YouTube quota guard | `test_quota_guard` |
| LLM disclosure | Default summariser is local; external provider requires opt-in consent (HTTP 412 otherwise) | `test_F3_external_llm_needs_consent` |
| Safe errors | Generic 500/502 bodies, no stack traces or provider messages | `main.py` |
| Log redaction | Tokens, API keys, emails masked; uvicorn arg shape preserved | `test_log_*` |
| Data deletion | `DELETE /me` hard-deletes rows + FTS index | `test_delete_all_user_data` |
| Duplicate/job safety | Dedupe keys, atomic claim, stale-lock recovery, backoff | `test_enqueue_idempotent`, `test_retry_backoff_*`, `test_job_runs_once_*` |

## Known gaps
- Tokens live in `localStorage` (XSS would expose them); no CSP headers are set yet.
- No email/password or OAuth login; signup is open unless `CKH_ALLOW_SIGNUP=false`.
- `POST /api/jobs/run` is a dev hook that any signed-in user can call (rate-limited); disable/guard it in production.
- SQLite in production is single-writer; use Postgres (`CKH_DATABASE_URL`) — FTS5 search falls back to `LIKE`-based title search there until a Postgres FTS backend is added.
- No dependency vulnerability scan is wired into CI yet.
