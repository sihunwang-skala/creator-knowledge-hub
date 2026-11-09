"""Domain services: channels, feed polling, quick add, sources, cross-check, deletion, takedown."""
import hashlib
from datetime import timedelta

from sqlalchemy.orm import Session

from . import search as fts
from .claims import SearchProvider, evaluate_claim, get_search_provider
from .db import utcnow
from .llm import tokens
from .models import (Channel, Claim, Evidence, KnowledgeChange, Note, Source, Subscription, TakedownRequest,
                     User, UserVideo, Video)
from .policy import AcquisitionMethod, apply_decision, evaluate_permission
from .security import sanitize_untrusted
from .transcript import parse_transcript
from .youtube import ChannelInfo, VideoInfo, extract_video_id, get_provider, parse_channel_input


# ---------- channels / feed ----------
def upsert_channel(db: Session, info: ChannelInfo) -> Channel:
    ch = db.query(Channel).filter_by(youtube_channel_id=info.youtube_channel_id).first()
    if not ch:
        ch = Channel(youtube_channel_id=info.youtube_channel_id)
        db.add(ch)
    ch.title, ch.handle, ch.description = info.title, info.handle, info.description
    ch.uploads_playlist_id, ch.is_demo, ch.fetched_at = info.uploads_playlist_id, info.is_demo, utcnow()
    db.flush()
    return ch


def upsert_video(db: Session, info: VideoInfo) -> Video:
    v = db.query(Video).filter_by(youtube_video_id=info.youtube_video_id).first()
    if not v:
        v = Video(youtube_video_id=info.youtube_video_id)
        db.add(v)
    ch = db.query(Channel).filter_by(youtube_channel_id=info.channel_id).first() if info.channel_id else None
    v.channel_id = ch.id if ch else v.channel_id
    v.title, v.description, v.published_at = info.title[:300], info.description, info.published_at
    v.duration_sec, v.language, v.youtube_license = info.duration_sec, info.language, info.youtube_license
    v.has_caption_flag, v.is_demo, v.fetched_at, v.metadata_available = info.has_caption_flag, info.is_demo, utcnow(), True
    db.flush()
    return v


def subscribe(db: Session, user: User, channel_input: str) -> Subscription:
    kind, value = parse_channel_input(channel_input)
    info = get_provider(db).resolve_channel(kind, value)
    if not info:
        raise LookupError("Channel not found")
    ch = upsert_channel(db, info)
    sub = db.query(Subscription).filter_by(user_id=user.id, channel_id=ch.id).first()
    if sub:
        return sub  # idempotent: no duplicates
    sub = Subscription(user_id=user.id, channel_id=ch.id)
    db.add(sub)
    db.commit()
    return sub


def _topic_match(sub: Subscription, v: Video) -> bool:
    if not sub.topics:
        return True
    toks = set(tokens(v.title + " " + v.description))
    return any(set(tokens(t)) & toks for t in sub.topics)


def poll_channel(db: Session, channel_id: int, max_results: int = 10) -> dict:
    """Discover uploads via the official API. Idempotent: existing user_videos are never duplicated or un-hidden."""
    ch = db.get(Channel, channel_id)
    if not ch:
        return {"new": 0}
    provider = get_provider(db)
    info = ChannelInfo(ch.youtube_channel_id, ch.title, ch.handle, ch.uploads_playlist_id, ch.description, ch.is_demo)
    new = 0
    subs = db.query(Subscription).filter_by(channel_id=ch.id).all()
    for vi in provider.list_uploads(info, max_results):
        vi.channel_id = ch.youtube_channel_id
        v = upsert_video(db, vi)
        for sub in subs:
            if not db.query(UserVideo).filter_by(user_id=sub.user_id, video_id=v.id).first():
                db.add(UserVideo(user_id=sub.user_id, video_id=v.id, topic_match=_topic_match(sub, v)))
                new += 1
    for sub in subs:
        sub.last_polled_at = utcnow()
    db.commit()
    return {"new": new}


def quick_add(db: Session, user: User, url: str) -> UserVideo:
    vid = extract_video_id(url)
    v = db.query(Video).filter_by(youtube_video_id=vid).first()
    if not v or (utcnow() - v.fetched_at).days >= 1:
        info = get_provider(db).get_video(vid)
        if info:
            if info.channel_id and not db.query(Channel).filter_by(youtube_channel_id=info.channel_id).first():
                pass  # channel metadata optional for quick add
            v = upsert_video(db, info)
        elif not v:
            # Metadata unavailable: still bookmark the ID (analysis stays blocked).
            v = Video(youtube_video_id=vid, title=f"YouTube video {vid}", metadata_available=False)
            db.add(v)
            db.flush()
    uv = db.query(UserVideo).filter_by(user_id=user.id, video_id=v.id).first()
    if not uv:
        uv = UserVideo(user_id=user.id, video_id=v.id)
        db.add(uv)
        db.flush()
    uv.state = "added"
    if uv.analysis_status == "not_started":
        has = db.query(Source).filter_by(user_id=user.id, video_id=v.id, status="approved").first()
        uv.analysis_status = "not_started" if has else "source_required"
    db.commit()
    return uv


# ---------- sources ----------
def add_source(db: Session, user: User, video: Video, *, method: str, content: str, filename: str = "",
               source_url: str = "", owner: str = "", license: str = "", permission_evidence: str = "",
               rights_attested: bool = False, retention_days: int = 365, provider: str = "") -> Source:
    clean, flags = sanitize_untrusted(content)
    try:
        segs, has_ts = parse_transcript(clean, filename)
    except ValueError as e:
        raise ValueError(str(e))
    if not segs:
        raise ValueError("No text found in source")
    src = Source(user_id=user.id, video_id=video.id, acquisition_method=method, source_url=source_url[:500], owner=owner[:200],
                 license=license[:80], permission_evidence=permission_evidence[:2000], rights_attested=rights_attested,
                 retention_days=max(1, min(retention_days, 3650)), has_timestamps=has_ts, content=clean,
                 content_hash=hashlib.sha256(clean.encode()).hexdigest(), injection_flags=flags,
                 citation={"title": video.title, "video_id": video.youtube_video_id, "owner": owner, "license": license, "url": source_url})
    apply_decision(src, evaluate_permission(method, license=license, rights_attested=rights_attested,
                                            permission_evidence=permission_evidence, source_url=source_url, provider=provider))
    db.add(src)
    uv = db.query(UserVideo).filter_by(user_id=user.id, video_id=video.id).first()
    if uv and uv.analysis_status in ("source_required", "not_started", "blocked") and src.status == "approved":
        uv.analysis_status = "not_started"
    elif uv and src.status != "approved":
        uv.analysis_status = "blocked" if src.status == "denied" else "source_required"
    db.commit()
    return src


def reevaluate_source(db: Session, src: Source, *, license: str | None, permission_evidence: str | None, rights_attested: bool | None) -> Source:
    if src.acquisition_method not in ("user_upload", "creator_provided", "licensed_distribution", "public_web", "podcast_rss", "user_note"):
        return src
    if license is not None:
        src.license = license[:80]
    if permission_evidence is not None:
        src.permission_evidence = permission_evidence[:2000]
    if rights_attested is not None:
        src.rights_attested = rights_attested
    apply_decision(src, evaluate_permission(src.acquisition_method, license=src.license, rights_attested=src.rights_attested,
                                            permission_evidence=src.permission_evidence, source_url=src.source_url))
    db.commit()
    return src


# ---------- cross-check ----------
def check_claim(db: Session, claim: Claim, provider: SearchProvider | None = None) -> Claim:
    provider = provider or get_search_provider()
    video = db.get(Video, claim.video_id)
    q = " ".join(dict.fromkeys(tokens(claim.text)))[:200]
    results = provider.search(q)
    verdict = evaluate_claim(claim.text, results, video.published_at if video else None)
    old = claim.verdict
    claim.evidence.clear()
    for r, stance, origin in verdict.evidence:
        claim.evidence.append(Evidence(url=r.url[:500], title=r.title[:300], snippet=r.snippet[:500], origin_key=origin[:200],
                                       stance=stance, published_at=r.published_at))
    claim.verdict, claim.rationale, claim.checked_at = verdict.verdict, verdict.rationale, utcnow()
    if verdict.verdict in ("contradicted", "outdated") and old != verdict.verdict:
        db.add(KnowledgeChange(user_id=claim.user_id, note_id=claim.note_id, kind="corrected",
                               detail=f"Claim marked {verdict.verdict}: {claim.text[:140]}"))
    db.commit()
    return claim


# ---------- deletion / takedown ----------
def delete_user_data(db: Session, user: User) -> None:
    """Hard-delete all of a user's data (account included)."""
    fts.unindex_user(db, user.id)
    for model in (Claim, Source):
        db.query(model).filter(model.user_id == user.id).delete()
    from .models import (Collection, CreatorOptIn, Digest, KnowledgeChange as KC, LlmUsage, NoteRevision, Synthesis)
    note_ids = [n.id for n in db.query(Note).filter_by(user_id=user.id)]
    if note_ids:
        db.query(NoteRevision).filter(NoteRevision.note_id.in_(note_ids)).delete(synchronize_session=False)
    for model in (Note, UserVideo, Subscription, Collection, Synthesis, Digest, KC, CreatorOptIn, LlmUsage):
        db.query(model).filter(model.user_id == user.id).delete()
    db.delete(user)
    db.commit()


def takedown(db: Session, video_id: str, contact: str, reason: str) -> TakedownRequest:
    """Precautionary quarantine: purge stored source text for the video, hide derived notes, log the request."""
    req = TakedownRequest(youtube_video_id=video_id, contact=contact[:200], reason=reason[:2000])
    db.add(req)
    v = db.query(Video).filter_by(youtube_video_id=video_id).first()
    if v:
        for s in db.query(Source).filter_by(video_id=v.id):
            s.content, s.status, s.policy_reason = "", "denied", "Takedown request received; content purged."
        for n in db.query(Note).filter_by(video_id=v.id):
            n.hidden_by_takedown = True
            fts_ok = n.id
        db.query(Claim).filter_by(video_id=v.id).delete()
    db.commit()
    return req


def purge_expired(db: Session) -> dict:
    """Retention + YouTube policy: drop expired source content; refresh-or-flag stale API metadata (>30 days)."""
    from .config import get_settings
    now = utcnow()
    purged = 0
    for s in db.query(Source).filter(Source.content != ""):
        if s.retention_days and s.retrieved_at + timedelta(days=s.retention_days) < now:
            s.content = ""
            purged += 1
    cutoff = now - timedelta(days=get_settings().metadata_max_age_days)
    refreshed = cleared = 0
    provider = get_provider(db)
    for v in db.query(Video).filter(Video.fetched_at < cutoff, Video.is_demo == False):  # noqa: E712
        info = None
        if not provider.is_demo:
            try:
                info = provider.get_video(v.youtube_video_id)
            except Exception:  # noqa: BLE001
                info = None
        if info:  # YouTube policy III.E.4: refresh stored API data at least every 30 days...
            upsert_video(db, info)
            refreshed += 1
        else:  # ...or delete it
            v.title, v.description, v.published_at = f"YouTube video {v.youtube_video_id}", "", None
            v.metadata_available = False
            v.fetched_at = now
            cleared += 1
    for ch in db.query(Channel).filter(Channel.fetched_at < cutoff, Channel.is_demo == False):  # noqa: E712
        ch.title, ch.description, ch.handle, ch.fetched_at = f"Channel {ch.youtube_channel_id}", "", "", now
        cleared += 1
    flagged = refreshed + cleared
    db.commit()
    return {"sources_purged": purged, "metadata_refreshed": refreshed, "metadata_cleared": cleared}
