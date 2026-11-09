from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import analysis, search as fts, services
from ..claims import get_search_provider
from ..config import get_settings
from ..db import get_db, utcnow
from ..deps import current_user, expensive, ip_limit
from ..digest import generate_digest
from ..exporting import digest_markdown, library_markdown, note_markdown, synthesis_markdown, video_url
from ..jobs import run_pending, schedule_tick
from ..llm import STYLES, tokens
from ..models import (Channel, Claim, Collection, CreatorOptIn, Digest, KnowledgeChange, Note, NoteRevision, Source,
                      Subscription, Synthesis, User, UserVideo, Video)
from ..policy import (ENABLED_METHODS, OPEN_LICENSES, PROHIBITED_METHODS, AcquisitionMethod, PermissionDenied)
from ..recommend import recommend
from ..schemas import *  # noqa: F401,F403
from ..security import SecurityError, hash_token, new_token, safe_fetch_text, validate_upload
from ..synthesis import build_synthesis
from ..youtube import (NotConfigured, QuotaExceeded, YouTubeError, extract_video_id, get_provider, quota_used)

router = APIRouter()


def iso(d):
    return d.isoformat() + "Z" if d else None


# ---------- serializers ----------
def out_video(v: Video) -> dict:
    return {"id": v.id, "youtube_video_id": v.youtube_video_id, "title": v.title, "description": v.description[:300],
            "channel": v.channel.title if v.channel else None, "channel_id": v.channel_id, "published_at": iso(v.published_at),
            "duration_sec": v.duration_sec, "language": v.language, "youtube_license": v.youtube_license,
            "has_caption_flag": v.has_caption_flag, "metadata_available": v.metadata_available, "is_demo": v.is_demo,
            "url": video_url(v.youtube_video_id), "embed_url": f"https://www.youtube.com/embed/{v.youtube_video_id}"}


def out_uv(u: UserVideo, has_source: bool | None = None) -> dict:
    status = u.analysis_status
    if status == "not_started" and has_source is False:
        status = "source_required"  # never imply a video is analysable without a permitted source
    return {"id": u.id, "state": u.state, "analysis_status": status, "topic_match": u.topic_match, "is_new": u.is_new,
            "discovered_at": iso(u.created_at), "video": out_video(u.video)}


def out_source(s: Source, with_preview: bool = False) -> dict:
    d = {"id": s.id, "video_id": s.video_id, "acquisition_method": s.acquisition_method, "source_url": s.source_url, "owner": s.owner,
         "license": s.license, "permission_scope": s.permission_scope, "status": s.status, "policy_reason": s.policy_reason,
         "rights_attested": s.rights_attested, "retrieved_at": iso(s.retrieved_at), "retention_days": s.retention_days,
         "has_timestamps": s.has_timestamps, "citation": s.citation, "content_available": bool(s.content),
         "injection_flags": s.injection_flags, "chars": len(s.content)}
    return d  # never returns the transcript body


def out_note(n: Note, full: bool = True) -> dict:
    d = {"id": n.id, "video": out_video(n.video), "style": n.style, "title": n.title, "tags": n.tags, "favorite": n.favorite,
         "version": n.version, "provider": n.provider, "model": n.model, "prompt_version": n.prompt_version,
         "generated_at": iso(n.generated_at), "collection_id": n.collection_id, "duplicate_of": n.duplicate_of,
         "source_id": n.source_id, "ai_generated": True}
    if full:
        d.update(points=n.points, action_items=n.action_items, glossary=n.glossary, user_notes=n.user_notes, edited_md=n.edited_md)
    else:
        d["preview"] = [p["text"] for p in n.points[:2]]
    return d


def out_claim(c: Claim) -> dict:
    return {"id": c.id, "note_id": c.note_id, "video_id": c.video_id, "text": c.text, "kind": c.kind, "priority": c.priority, "t": c.t,
            "verdict": c.verdict, "rationale": c.rationale, "checked_at": iso(c.checked_at),
            "evidence": [{"url": e.url, "title": e.title, "snippet": e.snippet, "stance": e.stance, "origin": e.origin_key,
                          "retrieved_at": iso(e.retrieved_at)} for e in c.evidence]}


def own(db: Session, model, id: int, user: User):
    obj = db.get(model, id)
    if not obj or getattr(obj, "user_id", user.id) != user.id:
        raise HTTPException(404, "Not found")
    return obj


def yt_errors(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except QuotaExceeded as e:
            raise HTTPException(429, str(e))
        except (YouTubeError, NotConfigured):
            raise HTTPException(502, "YouTube API request failed")
        except LookupError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))
    return wrapper


# ---------- health / users ----------
@router.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "demo_mode": s.demo_mode, "llm_provider": s.llm_provider, "search_provider": s.search_provider}


@router.post("/users", dependencies=[Depends(ip_limit)])
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if not get_settings().allow_signup:
        raise HTTPException(403, "Signup disabled")
    token = new_token()
    u = User(name=body.name.strip(), token_hash=hash_token(token))
    db.add(u)
    db.commit()
    return {"id": u.id, "name": u.name, "token": token}  # token shown once


def out_user(u: User) -> dict:
    return {"id": u.id, "name": u.name, "role_profile": u.role_profile, "interests": u.interests, "default_style": u.default_style,
            "llm_consent": u.llm_consent, "digest_frequency": u.digest_frequency}


@router.get("/me")
def me(user: User = Depends(current_user)):
    s = get_settings()
    return {**out_user(user), "demo_mode": s.demo_mode, "llm_provider": s.llm_provider, "styles": STYLES}


@router.patch("/me")
def patch_me(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    if "default_style" in data and data["default_style"] not in STYLES:
        raise HTTPException(422, "Unknown style")
    for k, v in data.items():
        setattr(user, k, v)
    db.commit()
    return out_user(user)


@router.delete("/me")
def delete_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    services.delete_user_data(db, user)
    return {"deleted": True}


@router.get("/policy")
def policy_info(user: User = Depends(current_user)):
    return {"enabled_methods": sorted(ENABLED_METHODS), "prohibited_methods": sorted(PROHIBITED_METHODS),
            "open_licenses": sorted(OPEN_LICENSES), "disabled": {"creator_oauth": "needs verified OAuth app",
                                                                 "external_provider": "unverified providers disabled"},
            "notice": "A user attestation is recorded but is not verification of rights or platform-term compliance."}


@router.get("/quota")
def quota(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from ..models import LlmUsage
    s = get_settings()
    row = db.get(LlmUsage, (user.id, utcnow().strftime("%Y-%m-%d")))
    return {"youtube": {"used": quota_used(db), "limit": s.youtube_daily_quota}, "llm": {"calls": row.calls if row else 0, "limit": s.llm_daily_call_limit},
            "stat_filters_enabled": s.enable_stat_filters}


# ---------- creators ----------
def out_sub(s: Subscription) -> dict:
    return {"id": s.id, "channel_id": s.channel_id, "title": s.channel.title, "handle": s.channel.handle, "description": s.channel.description,
            "is_demo": s.channel.is_demo, "favorite": s.favorite, "auto_process": s.auto_process, "topics": s.topics,
            "last_polled_at": iso(s.last_polled_at)}


@router.get("/creators")
def list_creators(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [out_sub(s) for s in db.query(Subscription).filter_by(user_id=user.id).order_by(Subscription.id)]


@router.get("/creators/search")
@yt_errors
def search_creators(q: str = Query(min_length=1, max_length=100), user: User = Depends(expensive), db: Session = Depends(get_db)):
    return [{"youtube_channel_id": c.youtube_channel_id, "title": c.title, "handle": c.handle, "description": c.description, "is_demo": c.is_demo}
            for c in get_provider(db).search_channels(q)]


@router.post("/creators")
@yt_errors
def add_creator(body: SubscribeIn, user: User = Depends(expensive), db: Session = Depends(get_db)):
    sub = services.subscribe(db, user, body.channel)
    services.poll_channel(db, sub.channel_id)
    return out_sub(sub)


@router.patch("/creators/{sid}")
def patch_creator(sid: int, body: SubscriptionPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    sub = own(db, Subscription, sid, user)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(sub, k, v)
    db.commit()
    return out_sub(sub)


@router.delete("/creators/{sid}")
def delete_creator(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(own(db, Subscription, sid, user))
    db.commit()
    return {"deleted": True}


# ---------- feed ----------
@router.get("/feed")
def feed(state: str = "discovered", channel_id: int | None = None, only_topic_match: bool = False, limit: int = Query(50, le=200),
         user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(UserVideo).join(Video).filter(UserVideo.user_id == user.id)
    q = q.filter(UserVideo.state != "hidden") if state == "all" else q.filter(UserVideo.state == state)
    if channel_id:
        q = q.filter(Video.channel_id == channel_id)
    if only_topic_match:
        q = q.filter(UserVideo.topic_match == True)  # noqa: E712
    rows = q.order_by(Video.published_at.desc()).limit(limit).all()
    approved = {r[0] for r in db.query(Source.video_id).filter(Source.user_id == user.id, Source.status == "approved")}
    return [out_uv(u, u.video_id in approved) for u in rows]


@router.post("/feed/refresh")
@yt_errors
def refresh_feed(user: User = Depends(expensive), db: Session = Depends(get_db)):
    total = 0
    for s in db.query(Subscription).filter_by(user_id=user.id):
        total += services.poll_channel(db, s.channel_id)["new"]
    return {"new": total}


@router.post("/videos/{uvid}/hide")
def hide(uvid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    u.state = "hidden"
    db.commit()
    return out_uv(u)


@router.post("/videos/{uvid}/unhide")
def unhide(uvid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    u.state = "discovered"
    db.commit()
    return out_uv(u)


@router.post("/videos/quick-add")
@yt_errors
def quick_add(body: QuickAddIn, user: User = Depends(expensive), db: Session = Depends(get_db)):
    return out_uv(services.quick_add(db, user, body.url))


@router.get("/videos/{uvid}")
def video_detail(uvid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    sources = db.query(Source).filter_by(user_id=user.id, video_id=u.video_id).order_by(Source.id)
    notes = db.query(Note).filter_by(user_id=user.id, video_id=u.video_id, hidden_by_takedown=False)
    has = any(s.status == "approved" for s in sources)
    return {**out_uv(u, has), "sources": [out_source(s) for s in sources], "notes": [out_note(n, False) for n in notes]}


# ---------- sources ----------
@router.post("/videos/{uvid}/sources/upload")
async def upload_source(uvid: int, file: UploadFile = File(...), acquisition_method: str = Form("user_upload"), license: str = Form(""),
                        owner: str = Form(""), source_url: str = Form(""), permission_evidence: str = Form(""),
                        rights_attested: bool = Form(False), retention_days: int = Form(365),
                        user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    s = get_settings()
    data = await file.read(s.max_upload_bytes + 1)
    try:
        text = validate_upload(file.filename or "", data, s.max_upload_bytes)
        src = services.add_source(db, user, u.video, method=acquisition_method, content=text, filename=file.filename or "",
                                  source_url=source_url, owner=owner, license=license, permission_evidence=permission_evidence,
                                  rights_attested=rights_attested, retention_days=retention_days)
    except (SecurityError, ValueError) as e:
        raise HTTPException(422, str(e))
    return out_source(src)


@router.post("/videos/{uvid}/sources/note")
def note_source(uvid: int, body: NoteSourceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    try:
        src = services.add_source(db, user, u.video, method=AcquisitionMethod.USER_NOTE, content=body.text, owner=user.name,
                                  license="user-authored", retention_days=3650)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return out_source(src)


@router.post("/videos/{uvid}/sources/web")
def web_source(uvid: int, body: WebSourceIn, user: User = Depends(expensive), db: Session = Depends(get_db)):
    s = get_settings()
    if not s.allow_web_fetch:
        raise HTTPException(403, "Web fetching disabled")
    u = own(db, UserVideo, uvid, user)
    try:
        text = safe_fetch_text(body.url, s.web_fetch_max_bytes)
        src = services.add_source(db, user, u.video, method=AcquisitionMethod.PUBLIC_WEB, content=text, source_url=body.url,
                                  owner=body.owner, license=body.license, permission_evidence=body.permission_evidence,
                                  retention_days=body.retention_days)
    except (SecurityError, ValueError) as e:
        raise HTTPException(422, str(e))
    except Exception:
        raise HTTPException(502, "Could not fetch the URL")
    return out_source(src)


@router.get("/videos/{uvid}/sources")
def list_sources(uvid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    return [out_source(s) for s in db.query(Source).filter_by(user_id=user.id, video_id=u.video_id)]


@router.post("/sources/{sid}/reevaluate")
def reevaluate(sid: int, body: ReevaluateIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    src = own(db, Source, sid, user)
    return out_source(services.reevaluate_source(db, src, license=body.license, permission_evidence=body.permission_evidence,
                                                 rights_attested=body.rights_attested))


@router.delete("/sources/{sid}")
def delete_source(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(own(db, Source, sid, user))
    db.commit()
    return {"deleted": True}


# ---------- analysis ----------
def _analyze_errors(fn):
    from functools import wraps

    @wraps(fn)
    def w(*a, **kw):
        try:
            return fn(*a, **kw)
        except HTTPException:
            raise
        except analysis.SourceRequired as e:
            raise HTTPException(409, {"code": "source_required", "message": str(e) or "A permitted source is required before analysis."})
        except PermissionDenied as e:
            raise HTTPException(403, {"code": "permission_" + e.status, "message": e.reason})
        except analysis.ConsentRequired as e:
            raise HTTPException(412, {"code": "consent_required", "message": str(e)})
        except analysis.BudgetExceeded as e:
            raise HTTPException(429, str(e))
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception:
            raise HTTPException(502, {"code": "analysis_unavailable", "message": "Analysis failed. Nothing was saved."})
    return w


@router.post("/videos/{uvid}/analyze")
@_analyze_errors
def analyze_video(uvid: int, body: AnalyzeIn, user: User = Depends(expensive), db: Session = Depends(get_db)):
    u = own(db, UserVideo, uvid, user)
    return out_note(analysis.analyze(db, user, u, body.style, body.source_id))


# ---------- notes / library ----------
@router.get("/notes")
def list_notes(q: str = "", tag: str = "", creator_id: int | None = None, collection_id: int | None = None, favorite: bool = False,
               limit: int = Query(100, le=300), user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Note).join(Video, Note.video_id == Video.id).filter(Note.user_id == user.id, Note.hidden_by_takedown == False)  # noqa: E712
    if q.strip():
        ids = fts.search_notes(db, user.id, q)
        query = query.filter(Note.id.in_(ids or [-1]))
    if creator_id:
        query = query.filter(Video.channel_id == creator_id)
    if collection_id:
        query = query.filter(Note.collection_id == collection_id)
    if favorite:
        query = query.filter(Note.favorite == True)  # noqa: E712
    notes = query.order_by(Note.generated_at.desc()).limit(limit).all()
    if tag:
        notes = [n for n in notes if tag.lower() in n.tags]
    return [out_note(n, False) for n in notes]


@router.get("/notes/{nid}")
def get_note(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    if n.hidden_by_takedown:
        raise HTTPException(451, "Unavailable due to a takedown request")
    return {**out_note(n), "claims": [out_claim(c) for c in db.query(Claim).filter_by(note_id=n.id)]}


@router.patch("/notes/{nid}")
def patch_note(nid: int, body: NotePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    data = body.model_dump(exclude_unset=True)
    if data.get("collection_id"):
        own(db, Collection, data["collection_id"], user)
    if "tags" in data and data["tags"] is not None:
        data["tags"] = sorted({t.strip().lower()[:40] for t in data["tags"] if t.strip()})
    if "edited_md" in data and data["edited_md"] is not None:
        db.add(NoteRevision(note_id=n.id, version=n.version, points=n.points, reason="user_edit"))
        n.version += 1
    for k, v in data.items():
        setattr(n, k, v)
    fts.index_note(db, n)
    db.commit()
    return out_note(n)


@router.delete("/notes/{nid}")
def delete_note(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    db.query(NoteRevision).filter_by(note_id=n.id).delete()
    db.delete(n)
    db.commit()
    return {"deleted": True}


@router.post("/notes/{nid}/regenerate")
@_analyze_errors
def regenerate(nid: int, user: User = Depends(expensive), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    u = db.query(UserVideo).filter_by(user_id=user.id, video_id=n.video_id).one()
    return out_note(analysis.analyze(db, user, u, n.style, n.source_id))


@router.get("/notes/{nid}/revisions")
def revisions(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    return [{"version": r.version, "reason": r.reason, "created_at": iso(r.created_at), "points": r.points}
            for r in db.query(NoteRevision).filter_by(note_id=n.id).order_by(NoteRevision.version.desc())]


@router.get("/notes/{nid}/related")
def related(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    mine = set(n.tags)
    scored = []
    for o in db.query(Note).filter(Note.user_id == user.id, Note.id != n.id, Note.hidden_by_takedown == False):  # noqa: E712
        shared = mine & set(o.tags)
        if shared:
            scored.append((len(shared), o, sorted(shared)))
    return [{**out_note(o, False), "shared_tags": sh} for _, o, sh in sorted(scored, key=lambda x: -x[0])[:8]]


@router.get("/notes/{nid}/export.md", response_class=PlainTextResponse)
def export_note(nid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    return note_markdown(n, db.query(Claim).filter_by(note_id=n.id, user_id=user.id).filter(Claim.verdict != "unchecked").all())


@router.get("/export/library.md", response_class=PlainTextResponse)
def export_library(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return library_markdown(db.query(Note).filter_by(user_id=user.id, hidden_by_takedown=False).order_by(Note.id).all())


@router.get("/collections")
def collections(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name} for c in db.query(Collection).filter_by(user_id=user.id)]


@router.post("/collections")
def create_collection(body: CollectionIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c = Collection(user_id=user.id, name=body.name.strip())
    db.add(c)
    db.commit()
    return {"id": c.id, "name": c.name}


@router.delete("/collections/{cid}")
def delete_collection(cid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(own(db, Collection, cid, user))
    db.commit()
    return {"deleted": True}


@router.get("/topics")
def topics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    from collections import Counter
    c = Counter(t for n in db.query(Note).filter_by(user_id=user.id, hidden_by_takedown=False) for t in n.tags)
    return [{"tag": t, "count": k} for t, k in c.most_common(100)]


@router.get("/history")
def history(limit: int = 50, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": k.id, "kind": k.kind, "detail": k.detail, "note_id": k.note_id, "created_at": iso(k.created_at)}
            for k in db.query(KnowledgeChange).filter_by(user_id=user.id).order_by(KnowledgeChange.id.desc()).limit(limit)]


# ---------- claims / cross-check ----------
@router.get("/claims")
def list_claims(verdict: str = "", user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = db.query(Claim).filter_by(user_id=user.id)
    if verdict:
        q = q.filter(Claim.verdict == verdict)
    return [out_claim(c) for c in q.order_by(Claim.priority.desc(), Claim.id).limit(200)]


@router.post("/claims/{cid}/check")
def check_claim(cid: int, user: User = Depends(expensive), db: Session = Depends(get_db)):
    c = own(db, Claim, cid, user)
    try:
        return out_claim(services.check_claim(db, c, get_search_provider()))
    except Exception:
        raise HTTPException(502, "Search provider failed; claim left unchecked")


@router.post("/notes/{nid}/crosscheck")
def crosscheck_note(nid: int, min_priority: int = 2, user: User = Depends(expensive), db: Session = Depends(get_db)):
    n = own(db, Note, nid, user)
    provider = get_search_provider()
    out = []
    for c in db.query(Claim).filter(Claim.note_id == n.id, Claim.priority >= min_priority).order_by(Claim.priority.desc()).limit(8):
        try:
            out.append(out_claim(services.check_claim(db, c, provider)))
        except Exception:
            out.append({**out_claim(c), "error": "search failed"})
    return out


# ---------- synthesis / digest ----------
@router.post("/synthesis")
def create_synthesis(body: SynthIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    notes = [own(db, Note, i, user) for i in body.note_ids]
    s = build_synthesis(db, user, body.topic, notes)
    return {"id": s.id, "topic": s.topic, "markdown": s.markdown, "stats": s.stats, "created_at": iso(s.created_at)}


@router.get("/synthesis")
def list_synthesis(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": s.id, "topic": s.topic, "markdown": s.markdown, "stats": s.stats, "created_at": iso(s.created_at)}
            for s in db.query(Synthesis).filter_by(user_id=user.id).order_by(Synthesis.id.desc())]


@router.get("/synthesis/{sid}/export.md", response_class=PlainTextResponse)
def export_synthesis(sid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return synthesis_markdown(own(db, Synthesis, sid, user))


@router.post("/digests")
def create_digest(frequency: str = Query("weekly", pattern="^(daily|weekly)$"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    d = generate_digest(db, user, frequency)
    return {"id": d.id, "frequency": d.frequency, "markdown": d.markdown, "created_at": iso(d.created_at)}


@router.get("/digests")
def list_digests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": d.id, "frequency": d.frequency, "markdown": d.markdown, "created_at": iso(d.created_at)}
            for d in db.query(Digest).filter_by(user_id=user.id).order_by(Digest.id.desc()).limit(30)]


@router.get("/digests/{did}/export.md", response_class=PlainTextResponse)
def export_digest(did: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return digest_markdown(own(db, Digest, did, user))


# ---------- discovery ----------
@router.get("/discover")
@yt_errors
def discover(q: str = Query(min_length=1, max_length=100), days: int | None = Query(None, ge=1, le=365), language: str = "",
             duration: str = Query("", pattern="^(|short|medium|long)$"), captions_only: bool = False, cc_only: bool = False,
             max_results: int = Query(10, ge=1, le=25), min_views: int | None = None, min_subscribers: int | None = None,
             user: User = Depends(expensive), db: Session = Depends(get_db)):
    if (min_views is not None or min_subscribers is not None) and not get_settings().enable_stat_filters:
        raise HTTPException(403, {"code": "filter_disabled", "message": "View/subscriber filters are disabled pending YouTube API policy review."})
    found = get_provider(db).search_videos(q, days=days, language=language, duration=duration, captions_only=captions_only,
                                           cc_only=cc_only, max_results=max_results)
    vids = [services.upsert_video(db, v) for v in found]
    db.commit()
    known = {u.video_id: u.state for u in db.query(UserVideo).filter_by(user_id=user.id)}
    recs = {v.id: s for v, s in recommend(db, user, vids, 100)}
    return [{**out_video(v), "recommendation_score": recs.get(v.id, 0), "library_state": known.get(v.id)} for v in vids]


# ---------- creator opt-in / takedown ----------
@router.post("/creator-optin")
def creator_optin(body: OptInIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    o = CreatorOptIn(user_id=user.id, **body.model_dump())
    db.add(o)
    db.commit()
    return {"id": o.id, "ownership_status": o.ownership_status,
            "note": "Ownership verification requires YouTube OAuth and is not implemented. Opt-in does not lift YouTube API restrictions."}


@router.get("/creator-optin")
def list_optin(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": o.id, "youtube_channel_id": o.youtube_channel_id, "allow_transcripts": o.allow_transcripts,
             "allow_commercial": o.allow_commercial, "transcript_license": o.transcript_license, "ownership_status": o.ownership_status}
            for o in db.query(CreatorOptIn).filter_by(user_id=user.id)]


@router.post("/takedown", dependencies=[Depends(ip_limit)])
def takedown(body: TakedownIn, db: Session = Depends(get_db)):
    try:
        vid = extract_video_id(body.video)
    except ValueError as e:
        raise HTTPException(422, str(e))
    r = services.takedown(db, vid, body.contact, body.reason)
    return {"id": r.id, "status": r.status}


# ---------- jobs ----------
@router.post("/jobs/run")
def run_jobs(user: User = Depends(expensive), db: Session = Depends(get_db)):
    """Dev/ops hook: enqueue due work and run it (the scheduler does this automatically when enabled)."""
    t = schedule_tick(db)
    return {**t, "ran": run_pending(db)}
