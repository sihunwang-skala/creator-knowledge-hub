# API integration guide

Interactive docs: run the server and open `http://127.0.0.1:8000/docs`.

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/users -H 'content-type: application/json' -d '{"name":"me"}' | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s -H "Authorization: Bearer $TOKEN" -X POST localhost:8000/api/creators -H 'content-type: application/json' -d '{"channel":"@syntheticdevlab"}'
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/feed
```

| Area | Endpoints |
|---|---|
| Account | `POST /users` · `GET/PATCH/DELETE /me` · `GET /policy` · `GET /quota` |
| Creators | `GET/POST /creators` · `GET /creators/search?q=` · `PATCH/DELETE /creators/{id}` |
| Feed | `GET /feed` · `POST /feed/refresh` · `POST /videos/{id}/hide\|unhide` · `POST /videos/quick-add` · `GET /videos/{id}` |
| Sources | `POST /videos/{id}/sources/upload\|note\|web` · `GET /videos/{id}/sources` · `POST /sources/{id}/reevaluate` · `DELETE /sources/{id}` |
| Analysis | `POST /videos/{id}/analyze` → 200 note · 409 `source_required` · 403 `permission_*` · 412 `consent_required` · 429 budget |
| Library | `GET /notes?q=&tag=&favorite=` · `GET/PATCH/DELETE /notes/{id}` · `POST /notes/{id}/regenerate` · `GET /notes/{id}/revisions\|related\|export.md` · `GET /export/library.md` · collections · `GET /topics` · `GET /history` |
| Verification | `GET /claims` · `POST /claims/{id}/check` · `POST /notes/{id}/crosscheck` |
| Synthesis/Digest | `POST/GET /synthesis` · `POST/GET /digests` · `…/export.md` |
| Discovery | `GET /discover?q=&days=&language=&duration=&captions_only=&cc_only=` |
| Compliance | `POST /creator-optin` · `POST /takedown` |
| Ops | `POST /jobs/run` (dev hook) |

## Plugging in real providers
- **YouTube:** set `CKH_YOUTUBE_API_KEY` (leaves demo mode).
- **LLM:** `CKH_LLM_PROVIDER=anthropic`, `CKH_ANTHROPIC_API_KEY=…`; each user must opt in under Settings. Cost ≈ one Messages call per analysis (transcript tokens in, ≤2k tokens out); capped by `CKH_LLM_DAILY_CALL_LIMIT`.
- **Search for cross-check:** `CKH_SEARCH_PROVIDER=brave`, `CKH_BRAVE_API_KEY=…` (Brave Search API is a paid/quota service; check current pricing).
- **New source/LLM/search adapters:** implement the small interfaces in `app/llm.py`, `app/claims.py`, `app/youtube.py` and register them in the `get_*` factory.
