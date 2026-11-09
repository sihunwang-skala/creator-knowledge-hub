"""YouTube integration. OFFICIAL Data API v3 only (no scraping, no caption download, no unofficial APIs).

Two adapters share one interface:
  * OfficialYouTubeProvider - needs CKH_YOUTUBE_API_KEY; every call is charged against a daily quota.
  * DemoYouTubeProvider     - synthetic channels/videos for demo & tests (clearly flagged is_demo).
Note: this module never retrieves captions/transcripts. Transcripts come only from permitted Sources.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy.orm import Session

from .config import get_settings
from .db import utcnow
from .models import QuotaUsage

API = "https://www.googleapis.com/youtube/v3"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
YT_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be", "www.youtu.be"}
# Per Google's quota table (checked 2026-11-09): list endpoints cost 1 unit; search.list has its own
# default bucket of 100 calls/day, separate from the 10,000-unit pool. Quotas reset at midnight Pacific.
COSTS = {"search": 1, "channels": 1, "playlistItems": 1, "videos": 1}


class YouTubeError(Exception):
    pass


class QuotaExceeded(YouTubeError):
    pass


class NotConfigured(YouTubeError):
    pass


@dataclass
class ChannelInfo:
    youtube_channel_id: str
    title: str
    handle: str = ""
    uploads_playlist_id: str = ""
    description: str = ""
    is_demo: bool = False


@dataclass
class VideoInfo:
    youtube_video_id: str
    title: str
    channel_id: str = ""
    description: str = ""
    published_at: datetime | None = None
    duration_sec: int = 0
    language: str = ""
    youtube_license: str = "youtube"
    has_caption_flag: bool = False
    is_demo: bool = False
    tags: list[str] = field(default_factory=list)


# ---------- input parsing / validation ----------
def extract_video_id(url_or_id: str) -> str:
    s = (url_or_id or "").strip()
    if VIDEO_ID_RE.match(s):
        return s
    p = urlparse(s if "://" in s else "https://" + s)
    if p.scheme not in ("http", "https") or (p.hostname or "").lower() not in YT_HOSTS:
        raise ValueError("Not a YouTube video URL")
    host = p.hostname.lower()
    vid = ""
    if host.endswith("youtu.be"):
        vid = p.path.strip("/").split("/")[0]
    elif p.path == "/watch":
        vid = (parse_qs(p.query).get("v") or [""])[0]
    else:
        m = re.match(r"^/(shorts|embed|live|v)/([^/?#]+)", p.path)
        vid = m.group(2) if m else ""
    if not VIDEO_ID_RE.match(vid):
        raise ValueError("Could not find a valid video ID in the URL")
    return vid


def parse_channel_input(s: str) -> tuple[str, str]:
    """Return (kind, value) where kind in {'id','handle','query'}."""
    s = (s or "").strip()
    if CHANNEL_ID_RE.match(s):
        return "id", s
    if s.startswith("@"):
        return "handle", s
    if "://" in s or "/" in s or s.lower().startswith(("youtube.com", "www.youtube.com", "m.youtube.com")):
        p = urlparse(s if "://" in s else "https://" + s)
        if (p.hostname or "").lower() not in YT_HOSTS:
            raise ValueError("Not a YouTube channel URL")
        m = re.match(r"^/channel/(UC[A-Za-z0-9_-]{22})", p.path)
        if m:
            return "id", m.group(1)
        m = re.match(r"^/(@[A-Za-z0-9._-]+)", p.path)
        if m:
            return "handle", m.group(1)
        raise ValueError("Unsupported channel URL format (use /channel/UC… or /@handle)")
    if not s:
        raise ValueError("Empty channel input")
    return "query", s


def parse_iso_duration(d: str) -> int:
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return dd * 86400 + h * 3600 + mi * 60 + s


# ---------- quota ----------
def today() -> str:
    return utcnow().strftime("%Y-%m-%d")


def quota_used(db: Session) -> int:
    row = db.get(QuotaUsage, (today(), "youtube"))
    return row.units if row else 0


def charge_quota(db: Session, endpoint: str) -> None:
    """Local guard (not authoritative: Google enforces the real quota, which resets at midnight Pacific)."""
    cost = COSTS[endpoint]
    settings = get_settings()
    service, limit = ("youtube_search", settings.youtube_search_daily_limit) if endpoint == "search" else ("youtube", settings.youtube_daily_quota)
    row = db.get(QuotaUsage, (today(), service))
    if row is None:
        row = QuotaUsage(day=today(), service=service, units=0)
        db.add(row)
    if row.units + cost > limit:
        raise QuotaExceeded(f"Daily YouTube API quota guard reached ({row.units}/{limit} for {service}).")
    row.units += cost
    db.commit()


# ---------- official adapter ----------
class OfficialYouTubeProvider:
    is_demo = False

    def __init__(self, db: Session, api_key: str, transport: httpx.BaseTransport | None = None):
        self.db, self.key, self.transport = db, api_key, transport

    def _get(self, endpoint: str, **params) -> dict:
        charge_quota(self.db, endpoint)
        with httpx.Client(timeout=15, transport=self.transport) as c:
            r = c.get(f"{API}/{endpoint}", params={**params, "key": self.key})
        if r.status_code == 403 and "quota" in r.text.lower():
            raise QuotaExceeded("YouTube reports the project quota is exhausted.")
        if r.status_code >= 400:
            raise YouTubeError(f"YouTube API error {r.status_code}")
        return r.json()

    @staticmethod
    def _channel(item: dict) -> ChannelInfo:
        sn = item.get("snippet", {})
        return ChannelInfo(item["id"] if isinstance(item["id"], str) else item["id"]["channelId"], sn.get("title", ""),
                           sn.get("customUrl", ""),
                           item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads", ""),
                           (sn.get("description") or "")[:500])

    def resolve_channel(self, kind: str, value: str) -> ChannelInfo | None:
        if kind == "query":
            res = self.search_channels(value, 1)
            return res[0] if res else None
        params = {"part": "snippet,contentDetails"}
        params["id" if kind == "id" else "forHandle"] = value
        items = self._get("channels", **params).get("items", [])
        return self._channel(items[0]) if items else None

    def search_channels(self, q: str, max_results: int = 5) -> list[ChannelInfo]:
        items = self._get("search", part="snippet", type="channel", q=q, maxResults=max_results).get("items", [])
        ids = [i["id"]["channelId"] for i in items]
        if not ids:
            return []
        full = self._get("channels", part="snippet,contentDetails", id=",".join(ids)).get("items", [])
        return [self._channel(i) for i in full]

    def _videos(self, ids: list[str]) -> list[VideoInfo]:
        if not ids:
            return []
        out = []
        for it in self._get("videos", part="snippet,contentDetails,status", id=",".join(ids[:50])).get("items", []):
            sn, cd = it.get("snippet", {}), it.get("contentDetails", {})
            pub = sn.get("publishedAt")
            out.append(VideoInfo(
                it["id"], sn.get("title", ""), sn.get("channelId", ""), (sn.get("description") or "")[:2000],
                datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None) if pub else None,
                parse_iso_duration(cd.get("duration", "")), sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
                it.get("status", {}).get("license", "youtube"), cd.get("caption") == "true", False, sn.get("tags", [])[:15]))
        return out

    def list_uploads(self, channel: ChannelInfo, max_results: int = 10) -> list[VideoInfo]:
        if not channel.uploads_playlist_id:
            return []
        items = self._get("playlistItems", part="contentDetails", playlistId=channel.uploads_playlist_id, maxResults=max_results).get("items", [])
        return self._videos([i["contentDetails"]["videoId"] for i in items])

    def get_video(self, video_id: str) -> VideoInfo | None:
        v = self._videos([video_id])
        return v[0] if v else None

    def search_videos(self, q: str, *, days: int | None = None, language: str = "", duration: str = "",
                      captions_only: bool = False, cc_only: bool = False, max_results: int = 10) -> list[VideoInfo]:
        params: dict = {"part": "snippet", "type": "video", "q": q, "maxResults": max(1, min(max_results, 25))}
        if days:
            params["publishedAfter"] = (utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        if language:
            params["relevanceLanguage"] = language
        if duration in ("short", "medium", "long"):
            params["videoDuration"] = duration
        if captions_only:
            params["videoCaption"] = "closedCaption"
        if cc_only:
            params["videoLicense"] = "creativeCommon"
        ids = [i["id"]["videoId"] for i in self._get("search", **params).get("items", [])]
        return self._videos(ids)


# ---------- demo adapter (synthetic; no network) ----------
_DEMO_CHANNELS = [
    ("UCdemoDevChannel00000001", "Synthetic Dev Lab", "@syntheticdevlab", "Demo channel about software architecture (synthetic)."),
    ("UCdemoFounderShow0000002", "Demo Founder Show", "@demofoundershow", "Demo channel about startups and pricing (synthetic)."),
    ("UCdemoScienceHour0000003", "Sample Science Hour", "@samplesciencehour", "Demo channel about science news (synthetic)."),
]
_DEMO_VIDEOS = {
    "UCdemoDevChannel00000001": [
        ("devDemo0001", "Designing a modular monolith (demo)", 1, 1260, "architecture modules boundaries"),
        ("devDemo0002", "Idempotent job queues explained (demo)", 3, 900, "queue retry idempotency backend"),
        ("devDemo0003", "SQLite for production side projects (demo)", 6, 780, "sqlite database postgres"),
    ],
    "UCdemoFounderShow0000002": [
        ("fndDemo0001", "Pricing a developer tool (demo)", 2, 1500, "pricing saas monetization"),
        ("fndDemo0002", "First 100 users without ads (demo)", 4, 1100, "growth users launch"),
    ],
    "UCdemoScienceHour0000003": [
        ("sciDemo0001", "How batteries age (demo)", 2, 840, "battery lithium research"),
        ("sciDemo0002", "Sleep and memory studies (demo)", 5, 960, "sleep memory research"),
    ],
}


class DemoYouTubeProvider:
    is_demo = True
    extra_videos: dict[str, list[VideoInfo]] = {}  # tests/demo can inject "new uploads"

    def _channel(self, row) -> ChannelInfo:
        return ChannelInfo(row[0], row[1], row[2], "UU" + row[0][2:], row[3], True)

    def resolve_channel(self, kind: str, value: str) -> ChannelInfo | None:
        for row in _DEMO_CHANNELS:
            if (kind == "id" and row[0] == value) or (kind == "handle" and row[2].lower() == value.lower()) or \
                    (kind == "query" and value.lower() in row[1].lower()):
                return self._channel(row)
        return None

    def search_channels(self, q: str, max_results: int = 5) -> list[ChannelInfo]:
        q = q.lower()
        return [self._channel(r) for r in _DEMO_CHANNELS if q in r[1].lower() or q in r[3].lower() or not q][:max_results]

    def _v(self, cid: str, vid: str, title: str, days: int, dur: int, tags: str) -> VideoInfo:
        return VideoInfo(vid, title, cid, f"Synthetic demo video. Topics: {tags}.", utcnow() - timedelta(days=days, hours=1),
                         dur, "en", "creativeCommon" if vid.endswith("1") else "youtube", True, True, tags.split())

    def _all(self, cid: str) -> list[VideoInfo]:
        return [self._v(cid, *row) for row in _DEMO_VIDEOS.get(cid, [])] + list(self.extra_videos.get(cid, []))

    def list_uploads(self, channel: ChannelInfo, max_results: int = 10) -> list[VideoInfo]:
        return sorted(self._all(channel.youtube_channel_id), key=lambda v: v.published_at or utcnow(), reverse=True)[:max_results]

    def get_video(self, video_id: str) -> VideoInfo | None:
        for row in _DEMO_CHANNELS:
            for v in self._all(row[0]):
                if v.youtube_video_id == video_id:
                    return v
        return None

    def search_videos(self, q: str, *, days: int | None = None, language: str = "", duration: str = "",
                      captions_only: bool = False, cc_only: bool = False, max_results: int = 10) -> list[VideoInfo]:
        words = q.lower().split()
        out = []
        for row in _DEMO_CHANNELS:
            for v in self._all(row[0]):
                hay = (v.title + " " + v.description).lower()
                if words and not any(w in hay for w in words):
                    continue
                if days and v.published_at and v.published_at < utcnow() - timedelta(days=days):
                    continue
                if cc_only and v.youtube_license != "creativeCommon":
                    continue
                if captions_only and not v.has_caption_flag:
                    continue
                if language and v.language and not v.language.startswith(language):
                    continue
                if duration == "short" and v.duration_sec > 240 or duration == "medium" and not 240 <= v.duration_sec <= 1200 \
                        or duration == "long" and v.duration_sec < 1200:
                    continue
                out.append(v)
        return out[:max_results]


def get_provider(db: Session):
    s = get_settings()
    if s.demo_mode:
        return DemoYouTubeProvider()
    return OfficialYouTubeProvider(db, s.youtube_api_key)
