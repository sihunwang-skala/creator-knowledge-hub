"""SQLAlchemy models. Every user-owned row carries user_id; queries always filter on it."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role_profile: Mapped[str] = mapped_column(String(120), default="")  # e.g. "software engineer"
    interests: Mapped[list] = mapped_column(JSON, default=list)
    default_style: Mapped[str] = mapped_column(String(40), default="brief")
    llm_consent: Mapped[bool] = mapped_column(Boolean, default=False)  # external LLM disclosure accepted
    digest_frequency: Mapped[str] = mapped_column(String(10), default="off")  # off|daily|weekly
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Channel(Base):
    """Public channel metadata from the YouTube Data API (shared, refreshed <=30 days)."""
    __tablename__ = "channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_channel_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    handle: Mapped[str] = mapped_column(String(100), default="")
    uploads_playlist_id: Mapped[str] = mapped_column(String(60), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_process: Mapped[bool] = mapped_column(Boolean, default=True)
    topics: Mapped[list] = mapped_column(JSON, default=list)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    channel: Mapped[Channel] = relationship()


class Video(Base):
    __tablename__ = "videos"
    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_video_id: Mapped[str] = mapped_column(String(11), unique=True, index=True)
    channel_id: Mapped[int | None] = mapped_column(ForeignKey("channels.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(10), default="")
    youtube_license: Mapped[str] = mapped_column(String(30), default="youtube")  # youtube|creativeCommon
    has_caption_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_available: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    channel: Mapped[Channel | None] = relationship()


class UserVideo(Base):
    """A user's relationship to a video: discovered in feed, added to library, or hidden."""
    __tablename__ = "user_videos"
    __table_args__ = (UniqueConstraint("user_id", "video_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    state: Mapped[str] = mapped_column(String(12), default="discovered")  # discovered|added|hidden
    # not_started|source_required|analysis_unavailable|processing|done|blocked
    analysis_status: Mapped[str] = mapped_column(String(24), default="not_started")
    topic_match: Mapped[bool] = mapped_column(Boolean, default=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    video: Mapped[Video] = relationship()


class Source(Base):
    """A content source (transcript/note/etc.) with provenance + permission decision."""
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    acquisition_method: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str] = mapped_column(String(500), default="")
    owner: Mapped[str] = mapped_column(String(200), default="")
    license: Mapped[str] = mapped_column(String(80), default="")
    permission_scope: Mapped[str] = mapped_column(String(60), default="")
    permission_evidence: Mapped[str] = mapped_column(Text, default="")
    rights_attested: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # approved|pending|denied
    policy_reason: Mapped[str] = mapped_column(Text, default="")
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    retention_days: Mapped[int] = mapped_column(Integer, default=365)
    citation: Mapped[dict] = mapped_column(JSON, default=dict)
    has_timestamps: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[str] = mapped_column(Text, default="")  # private; never exported or committed
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    injection_flags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    style: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    points: Mapped[list] = mapped_column(JSON, default=list)  # [{text, kind, cites, t}]
    action_items: Mapped[list] = mapped_column(JSON, default=list)
    glossary: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    user_notes: Mapped[str] = mapped_column(Text, default="")
    edited_md: Mapped[str | None] = mapped_column(Text, nullable=True)  # user override of AI text
    version: Mapped[int] = mapped_column(Integer, default=1)
    provider: Mapped[str] = mapped_column(String(60), default="")
    model: Mapped[str] = mapped_column(String(80), default="")
    prompt_version: Mapped[str] = mapped_column(String(20), default="")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"), nullable=True)
    duplicate_of: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden_by_takedown: Mapped[bool] = mapped_column(Boolean, default=False)
    video: Mapped[Video] = relationship()


class NoteRevision(Base):
    __tablename__ = "note_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    points: Mapped[list] = mapped_column(JSON, default=list)
    reason: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KnowledgeChange(Base):
    """Knowledge history: added / updated / corrected entries shown in digests."""
    __tablename__ = "knowledge_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    note_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # added|updated|corrected|removed
    detail: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    note_id: Mapped[int] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"))
    text: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(30), default="statistic")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    t: Mapped[float | None] = mapped_column(Float, nullable=True)
    # unchecked|supported|partially_supported|contradicted|insufficient_evidence|outdated
    verdict: Mapped[str] = mapped_column(String(30), default="unchecked")
    rationale: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    evidence: Mapped[list["Evidence"]] = relationship(cascade="all, delete-orphan")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("claims.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(300), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    origin_key: Mapped[str] = mapped_column(String(200), default="")  # independence grouping
    stance: Mapped[str] = mapped_column(String(12), default="neutral")  # supports|contradicts|neutral
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Synthesis(Base):
    __tablename__ = "syntheses"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic: Mapped[str] = mapped_column(String(200))
    note_ids: Mapped[list] = mapped_column(JSON, default=list)
    markdown: Mapped[str] = mapped_column(Text, default="")
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Digest(Base):
    __tablename__ = "digests"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    frequency: Mapped[str] = mapped_column(String(10), default="weekly")
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(200), unique=True)  # idempotency
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(10), default="queued", index=True)  # queued|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=4)
    run_after: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QuotaUsage(Base):
    __tablename__ = "quota_usage"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    service: Mapped[str] = mapped_column(String(20), primary_key=True)
    units: Mapped[int] = mapped_column(Integer, default=0)


class LlmUsage(Base):
    __tablename__ = "llm_usage"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class CreatorOptIn(Base):
    """Creator registration. Ownership verification is NOT implemented (needs YouTube OAuth)."""
    __tablename__ = "creator_optins"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    youtube_channel_id: Mapped[str] = mapped_column(String(40))
    contact: Mapped[str] = mapped_column(String(200), default="")
    allow_transcripts: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_commercial: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript_license: Mapped[str] = mapped_column(String(80), default="")
    ownership_status: Mapped[str] = mapped_column(String(30), default="unverified")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TakedownRequest(Base):
    __tablename__ = "takedown_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    youtube_video_id: Mapped[str] = mapped_column(String(11), index=True)
    contact: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="quarantined")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
