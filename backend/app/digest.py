from collections import Counter
from datetime import timedelta

from sqlalchemy.orm import Session

from .db import utcnow
from .exporting import DISCLAIMER, video_url
from .models import Claim, Digest, KnowledgeChange, Note, User, UserVideo


def generate_digest(db: Session, user: User, frequency: str | None = None) -> Digest:
    freq = frequency or (user.digest_frequency if user.digest_frequency != "off" else "weekly")
    end = utcnow()
    start = end - timedelta(days=1 if freq == "daily" else 7)
    uvs = db.query(UserVideo).filter(UserVideo.user_id == user.id, UserVideo.created_at >= start, UserVideo.state != "hidden").all()
    notes = db.query(Note).filter(Note.user_id == user.id, Note.generated_at >= start, Note.hidden_by_takedown == False).all()  # noqa: E712
    changes = db.query(KnowledgeChange).filter(KnowledgeChange.user_id == user.id, KnowledgeChange.created_at >= start).all()
    claims = db.query(Claim).filter(Claim.user_id == user.id, Claim.checked_at >= start).all()
    tag_counts = Counter(t for n in notes for t in n.tags)
    L = [f"# {freq.capitalize()} Digest", "", f"Period: {start:%Y-%m-%d} → {end:%Y-%m-%d}", "", DISCLAIMER, ""]
    L += ["## New videos discovered", ""] + ([f"- [{u.video.title}]({video_url(u.video.youtube_video_id)}) - {u.video.channel.title if u.video.channel else ''}" for u in uvs] or ["- _None this period._"])
    L += ["", "## New knowledge added", ""] + ([f"- {n.title} ({n.provider})" for n in notes] or ["- _No new notes._"])
    tips = [(a, n) for n in notes for a in n.action_items[:2]]
    L += ["", "## Practical tips", ""] + ([f"- {a} ([{n.video.title}]({video_url(n.video.youtube_video_id)}))" for a, n in tips[:8]] or ["- _None._"])
    L += ["", "## Recurring themes", ""] + ([f"- **{t}** ({c} notes)" for t, c in tag_counts.most_common(6) if c >= 2] or ["- _No topic repeated across notes._"])
    L += ["", "## What changed", ""] + ([f"- {c.kind}: {c.detail}" for c in changes if c.kind in ("updated", "corrected")] or ["- _No updates._"])
    L += ["", "## Notable claims & verification", ""]
    for c in claims:
        L.append(f"- **{c.verdict}**: {c.text}")
        for e in c.evidence[:2]:
            L.append(f"  - [{e.title or e.url}]({e.url})")
    if not claims:
        L.append("- _No claims checked this period._")
    L += ["", "## Recommended action items", ""] + ([f"- [ ] {a}" for a, _ in tips[:6]] or ["- _None._"])
    L += ["", "## References", ""] + [f"- [{n.video.title}]({video_url(n.video.youtube_video_id)})" for n in notes]
    d = Digest(user_id=user.id, frequency=freq, period_start=start, period_end=end, markdown="\n".join(L) + "\n")
    db.add(d)
    db.commit()
    return d
