# Content rights & provenance

## Principle
Permission is evaluated **per source** and enforced in code before any AI step: `analysis.analyze()` → `policy.assert_analyzable()`. Unapproved content never reaches a summarizer, and a video with no approved source is never "summarised" from its title/description (`Source Required` / `Analysis Unavailable` / `Permission Required` states).

## Acquisition methods (`app/policy.py`)
| Method | Result |
|---|---|
| `user_note` (user's own writing) | approved |
| `user_upload` | needs attestation **and** a stated basis (license or evidence) → approved for *private analysis only*, scope `private_analysis_user_attested`; attestation without basis → `pending`; no attestation → `denied` |
| `creator_provided` | needs written permission evidence → else `pending` |
| `licensed_distribution`, `public_web`, `podcast_rss` | approved only with an open transcript license (CC0, CC-BY, CC-BY-SA, CC-BY-NC, public domain) and an https URL; unknown/"all rights reserved"/YouTube standard → `pending`; `public_web`/`podcast_rss` may also be approved with documented explicit permission |
| `creator_oauth` | **disabled** (needs a verified OAuth app) |
| `external_provider` (third-party transcript APIs) | **disabled**; `VERIFIED_EXTERNAL_PROVIDERS` is intentionally empty |
| `youtube_caption_download`, `video_download_stt`, `scraping`, `unofficial_api`, `captcha_bypass` | **prohibited**, never approvable |

`pending` sources are never auto-approved; the user can add evidence and re-evaluate (`POST /sources/{id}/reevaluate`), which re-runs the same policy.

## Limits of attestation
A checkbox is a record, not verification. It narrows scope to private use and is stored with the source (`rights_attested`, `permission_scope`, `policy_reason`), but it does not prove ownership or YouTube ToS compliance. The UI says so.

## Provenance recorded per source
Source URL · owner · license · permission scope · permission evidence · acquisition method · retrieved at · retention days (content is purged after expiry by `purge_expired`) · citation metadata (title, video id, owner, license, url) · timestamp availability · content hash · injection flags.
Every note records provider, model and prompt version; each key point is tagged `source` (with segment citations) or `ai_added`. Citation validation downgrades uncited "source" points.

## Output discipline
- Local summarizer never emits more than ~35 % of a source's words and clips each point to 160 chars; LLM output is rejected if it echoes >50 %.
- Exports (`*.md`) contain AI notes and links, never the stored transcript.
- Source text is stored only in the user's private row, is never returned by the API (`content_available` only), and is git-ignored in practice (`transcripts/`, `data/`).

## Removal
`DELETE /sources/{id}`, `DELETE /me`, and `POST /api/takedown` (public form for rights holders): purges stored source text for that video across all users, hides derived notes, deletes derived claims, and logs the request for manual review. Quarantine is precautionary and unauthenticated by design; abuse handling is future work.
