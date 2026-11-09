"""AI analysis pipeline. The ONLY entry to summarisation is `analyze` -> policy.assert_analyzable()."""
import hashlib
import re

from sqlalchemy.orm import Session

from . import search as fts
from .config import get_settings
from .db import utcnow
from .llm import PROMPT_VERSION, STYLES, SummaryRequest, get_llm, tokens, validate_citations
from .claims import extract_claims
from .models import Claim, KnowledgeChange, Note, NoteRevision, Source, User, UserVideo, Video
from .policy import PermissionDenied, assert_analyzable
from .security import sanitize_untrusted
from .transcript import parse_transcript


class SourceRequired(Exception):
    pass


class ConsentRequired(Exception):
    pass


class BudgetExceeded(Exception):
    pass


def llm_budget_charge(db: Session, user: User) -> None:
    from .models import LlmUsage
    day = utcnow().strftime("%Y-%m-%d")
    row = db.get(LlmUsage, (user.id, day))
    if row is None:
        row = LlmUsage(user_id=user.id, day=day, calls=0)
        db.add(row)
    if row.calls >= get_settings().llm_daily_call_limit:
        raise BudgetExceeded("Daily LLM call limit reached.")
    row.calls += 1
    db.commit()


def pick_source(db: Session, user: User, video: Video, source_id: int | None) -> Source:
    q = db.query(Source).filter(Source.user_id == user.id, Source.video_id == video.id)
    if source_id is not None:
        src = q.filter(Source.id == source_id).first()
        if not src:
            raise SourceRequired("Source not found for this video.")
        return src
    sources = q.order_by(Source.id.desc()).all()
    if not sources:
        raise SourceRequired("No permitted source has been attached to this video.")
    for s in sources:
        if s.status == "approved":
            return s
    raise PermissionDenied(sources[0].status, sources[0].policy_reason)


def _point_key(text: str) -> frozenset:
    return frozenset(tokens(text))


def _similar(a: frozenset, b: frozenset, th: float = 0.7) -> bool:
    return bool(a | b) and len(a & b) / len(a | b) >= th


def analyze(db: Session, user: User, uv: UserVideo, style: str = "brief", source_id: int | None = None, llm=None) -> Note:
    if style not in STYLES:
        raise ValueError(f"Unknown style '{style}'")
    video = uv.video
    try:
        source = pick_source(db, user, video, source_id)
        assert_analyzable(source)  # <-- rights gate: nothing past this line runs for unpermitted content
    except SourceRequired:
        uv.analysis_status = "source_required"
        db.commit()
        raise
    except PermissionDenied:
        uv.analysis_status = "blocked"
        db.commit()
        raise
    llm = llm or get_llm()
    if llm.external and not user.llm_consent:
        raise ConsentRequired("Enable 'send transcript text to the configured LLM provider' in Settings first.")
    if llm.external:
        llm_budget_charge(db, user)
    uv.analysis_status = "processing"
    db.commit()
    try:
        segments, _ = parse_transcript(source.content, "", get_settings().max_segments)
        # re-parse with timestamps if the stored content is SRT/VTT
        if "-->" in source.content[:2000]:
            segments, _ = parse_transcript(source.content, "x.srt", get_settings().max_segments)
        clean = []
        for s in segments:
            s.text, _flags = sanitize_untrusted(s.text)
            clean.append(s)
        if not clean:
            uv.analysis_status = "analysis_unavailable"
            db.commit()
            raise SourceRequired("Source contains no analysable text.")
        req = SummaryRequest(style, video.title, clean, user.role_profile, user.interests or [])
        summary = llm.summarize(req)
        words = sum(len(s.text.split()) for s in clean)
        summary, warnings = validate_citations(summary, len(clean), source_words=words)
    except SourceRequired:
        raise
    except Exception:
        uv.analysis_status = "analysis_unavailable"
        db.commit()
        raise

    points = [p.model_dump() for p in summary.points]
    existing = db.query(Note).filter(Note.user_id == user.id, Note.video_id == video.id, Note.style == style).first()
    if existing:
        old_keys = [_point_key(p["text"]) for p in existing.points]
        new_keys = [_point_key(p["text"]) for p in points]
        added = sum(1 for k in new_keys if not any(_similar(k, o) for o in old_keys))
        removed = sum(1 for o in old_keys if not any(_similar(o, k) for k in new_keys))
        db.add(NoteRevision(note_id=existing.id, version=existing.version, points=existing.points, reason="regenerate"))
        existing.version += 1
        note = existing
        db.add(KnowledgeChange(user_id=user.id, note_id=note.id, kind="updated",
                               detail=f"'{video.title}' regenerated ({style}): +{added} new, -{removed} dropped points"))
    else:
        note = Note(user_id=user.id, video_id=video.id, style=style, title="")
        db.add(note)
        db.flush()
    note.source_id, note.title = source.id, summary.title
    note.points, note.action_items = points, summary.action_items
    note.glossary = [g.model_dump() for g in summary.glossary]
    note.tags = sorted(set(t.lower() for t in summary.tags))[:12]
    note.provider, note.model, note.prompt_version, note.generated_at = llm.name, llm.model, PROMPT_VERSION, utcnow()
    if not existing:
        db.add(KnowledgeChange(user_id=user.id, note_id=note.id, kind="added", detail=f"Added note '{video.title}' ({style})"))
        # duplicate detection against other notes
        mine = [_point_key(p["text"]) for p in points]
        for other in db.query(Note).filter(Note.user_id == user.id, Note.id != note.id).all():
            okeys = [_point_key(p["text"]) for p in other.points]
            if mine and sum(1 for k in mine if any(_similar(k, o, 0.6) for o in okeys)) / len(mine) >= 0.6:
                note.duplicate_of = other.id
                break
    # claims
    db.query(Claim).filter(Claim.note_id == note.id, Claim.verdict == "unchecked").delete()
    have = {c.text for c in db.query(Claim).filter(Claim.note_id == note.id)}
    for c in extract_claims(clean):
        if c.text not in have:
            db.add(Claim(user_id=user.id, note_id=note.id, video_id=video.id, text=c.text, kind=c.kind, priority=c.priority, t=c.t))
    uv.analysis_status, uv.state = "done", "added"
    db.flush()
    fts.index_note(db, note)
    db.commit()
    return note
