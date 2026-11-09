# YouTube API policy notes

> Engineering notes, **not legal advice**. Compliance is not guaranteed. Re-check the sources before production use.

| Rule (official section) | Source (checked) | How this project handles it |
|---|---|---|
| Stored API data must be refreshed or deleted within 30 calendar days (Developer Policies III.E.4.c/d) | <https://developers.google.com/youtube/terms/developer-policies> (checked 2026-11-09) | `Video`/`Channel` rows carry `fetched_at`. The `purge_expired` job re-fetches via the official API when a key is configured, otherwise blanks title/description/handle (`services.purge_expired`, test `test_stale_api_metadata_deleted_after_30_days`). **Gap:** note titles that embed a video title are AI-generated user content and are not rewritten. |
| No scraping, no undocumented APIs, no other technology to retrieve API data (III.E.6, III.D.7, III.I.14) | same | Only `googleapis.com/youtube/v3` is called (`app/youtube.py`). There is no HTML fetching of youtube.com and no caption/transcript endpoint. `youtube_caption_download`, `scraping`, `unofficial_api` are hard-denied acquisition methods (`app/policy.py`). |
| No downloading/caching of YouTube audiovisual content (III.E.1.a) | same | Nothing is downloaded. `video_download_stt` is a denied method. Playback uses the official embed (`youtube-nocookie.com/embed`) only after the user clicks "Show player". |
| No new/derived metrics from API data (III.E.4.h) | same | View-count and subscriber-count filters are **disabled by default** (`CKH_ENABLE_STAT_FILTERS=false`, HTTP 403 `filter_disabled`). The recommendation score is a personal relevance number computed from the user's own interests/tags matched against title text; it is never shown as popularity/engagement. Treat this as a residual risk (see below). |
| User data deletion within 7 days of request (III.E.4.g) | same | `DELETE /api/me` removes everything immediately, including full-text index rows. |
| Quota | <https://developers.google.com/youtube/v3/determine_quota_cost> (checked 2026-11-09) | list endpoints = 1 unit; `search.list` has its own 100-calls/day bucket; default pool 10,000 units/day; resets midnight Pacific. `charge_quota` is a *local guard* (UTC day), Google enforces the real limit. |
| Terms of Service / API Services ToS | <https://www.youtube.com/t/terms>, <https://developers.google.com/youtube/terms/api-services-terms-of-service> | **Not re-read in this session.** Listed so a reviewer knows what to verify. |

## Captions and transcripts
The Data API's caption download requires the video owner's authorization. This project does **not** attempt caption retrieval for third-party videos. Transcripts come only from permitted `Source`s (see `CONTENT_RIGHTS.md`). A video's Creative Commons flag (`status.license = creativeCommon`) describes the *video*, is stored for filtering/provenance, and is **not** treated as permission to obtain or reuse its captions.

## Scheduled polling
`playlistItems.list` on the uploads playlist (1 unit) per channel per hour at most (idempotent job key `poll:<channel>:<YYYYMMDDHH>`), plus 1 unit for `videos.list`. 100 followed channels ≈ 200 units/hour at the extreme ≈ 4,800/day, inside the default quota. Set `CKH_YOUTUBE_DAILY_QUOTA` lower for a safety margin.

## Residual risks
- Quota/derived-metric rules can change; the audited-developer exceptions (III.L) are not used.
- Creator opt-in does **not** lift API restrictions; it only supplies a license for transcript text.
- A production deployment needs the API Services compliance audit/quota extension process if usage grows.
