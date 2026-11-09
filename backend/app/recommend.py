"""Content-based recommendations using only explicit signals (interests, saved tags, favourite creators).
No data is shared with or sold to third parties; no engagement scoring from YouTube statistics."""
from collections import Counter

from sqlalchemy.orm import Session

from .llm import tokens
from .models import Note, Subscription, User, UserVideo, Video


def profile_terms(db: Session, user: User) -> Counter:
    c: Counter = Counter()
    for i in user.interests or []:
        for t in tokens(i):
            c[t] += 3
    for n in db.query(Note).filter(Note.user_id == user.id).all():
        for t in n.tags:
            c[t] += 1
        if n.favorite:
            for t in n.tags:
                c[t] += 2
    return c


def score_video(db: Session, user: User, video: Video, terms: Counter, fav_channels: set[int]) -> float:
    toks = set(tokens(video.title + " " + video.description))
    s = sum(w for t, w in terms.items() if t in toks)
    if video.channel_id in fav_channels:
        s += 2
    return float(s)


def recommend(db: Session, user: User, candidates: list[Video], limit: int = 10) -> list[tuple[Video, float]]:
    terms = profile_terms(db, user)
    fav = {s.channel_id for s in db.query(Subscription).filter(Subscription.user_id == user.id, Subscription.favorite == True)}  # noqa: E712
    known = {u.video_id for u in db.query(UserVideo).filter(UserVideo.user_id == user.id)}
    scored = [(v, score_video(db, user, v, terms, fav)) for v in candidates if v.id not in known]
    return sorted([x for x in scored if x[1] > 0], key=lambda x: -x[1])[:limit]
