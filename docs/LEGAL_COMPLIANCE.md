# Legal & compliance checklist

This project reduces, but cannot eliminate, copyright and platform-policy risk. **It does not claim legal compliance.** Have counsel review before any commercial launch.

| # | Requirement | Status | Where |
|---|---|---|---|
| 1 | Follow YouTube ToS / API policy | Designed for; ToS text not re-read this session | `YOUTUBE_API_POLICY.md` |
| 2 | No unauthorised caption downloading | Enforced (no capability exists; method denied) | `policy.py` |
| 3 | No scraping / unofficial APIs / CAPTCHA bypass | Enforced; only `googleapis.com/youtube/v3` + user-supplied https docs via SSRF-guarded fetch | `youtube.py`, `security.py` |
| 4 | No download + STT workaround | Denied method | `policy.py` |
| 5 | Third-party transcript APIs not assumed lawful | Disabled | `policy.py` |
| 6 | CC video license ≠ YouTube data access | Implemented distinction | `policy.py`, tests |
| 7 | Attribution ≠ permission | Attribution kept, never treated as approval | `policy.py` |
| 8 | Permission per source | Implemented | `Source.status` |
| 9 | No public re-posting of transcripts | `.gitignore`, API never returns text, repo holds only self-authored `samples/` | `.gitignore`, `samples/README.md` |
| 10 | Independent summaries, limited reproduction | Output-share caps + validation | `llm.py` |
| 11 | Link to original / official player | Yes; embed on demand | `VideoDetail.tsx` |
| 12 | Takedown + user data deletion | Implemented | `/api/takedown`, `/api/me` |
| 13 | Distinguish source vs AI content | `source` vs `ai_added`, labels in UI/exports | `llm.py`, `exporting.py` |
| 14 | No accuracy guarantee | Disclaimer on every note/export/digest | `exporting.py` |
| 15 | Private by default | Per-user scoping on every query; tested | `tests/test_scenarios.py` |

## Open items (not solved)
- Fair use/quotation limits vary by jurisdiction; the summariser caps are engineering heuristics.
- Korean and EU rules (PIPA/GDPR) on user data are not formally assessed; the app stores a display name and an opaque token only.
- Takedown handling is automatic quarantine with no identity verification of the requester.
- Creator revenue sharing/payments are intentionally **not** implemented.
