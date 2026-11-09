"""Knowledge synthesis across notes: common / differing / new / duplicate / conflicting, with source links."""
import re
from datetime import datetime

from sqlalchemy.orm import Session

from .claims import NUM_RE
from .db import utcnow
from .exporting import DISCLAIMER, video_url
from .llm import tokens
from .models import Claim, KnowledgeChange, Note, Synthesis, User


def _tok(t: str) -> frozenset:
    return frozenset(tokens(NUM_RE.sub(" ", t)))


def _j(a, b) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _nums(t: str) -> set[str]:
    return {n.replace(",", "") for n in NUM_RE.findall(t)}


def build_synthesis(db: Session, user: User, topic: str, notes: list[Note]) -> Synthesis:
    items = []  # (tokens, text, note, point)
    total_points = 0
    for n in notes:
        for p in n.points:
            total_points += 1
            items.append((_tok(p["text"]), p["text"], n, p))
    clusters: list[list] = []
    for it in items:
        for c in clusters:
            if _j(it[0], c[0][0]) >= 0.5:
                c.append(it)
                break
        else:
            clusters.append([it])
    deduped = total_points - len(clusters)

    def ref(it) -> str:
        n, p = it[2], it[3]
        return f"[{n.video.title}]({video_url(n.video.youtube_video_id, p.get('t'))})"

    common, unique, conflicts = [], [], []
    for c in clusters:
        vids = {it[2].video_id for it in c}
        (common if len(vids) >= 2 else unique).append(c)
    for i, a in enumerate(clusters):
        for b in clusters[i + 1:]:
            if {x[2].video_id for x in a} & {x[2].video_id for x in b}:
                continue
            sim = _j(a[0][0], b[0][0])
            na, nb = _nums(a[0][1]), _nums(b[0][1])
            if 0.25 <= sim < 0.5 and na and nb and not (na & nb):
                conflicts.append((a[0], b[0]))
    newest = max(notes, key=lambda n: n.generated_at) if notes else None
    new_items = [c[0] for c in unique if newest and c[0][2].id == newest.id][:5]
    cases = [c[0] for c in clusters if re.search(r"\b(example|case|for instance|story)\b", c[0][1], re.I)][:5]
    actions: list[str] = []
    seen = []
    for n in notes:
        for a in n.action_items:
            k = _tok(a)
            if not any(_j(k, s) >= 0.6 for s in seen):
                seen.append(k)
                actions.append(a)
    claims = db.query(Claim).filter(Claim.user_id == user.id, Claim.note_id.in_([n.id for n in notes]), Claim.verdict != "unchecked").all()

    L = [f"# Synthesis: {topic}", "", DISCLAIMER, "", f"Based on {len(notes)} note(s) from {len({n.video.channel_id for n in notes})} creator(s); generated {utcnow():%Y-%m-%d}.", ""]
    L += ["## Common knowledge", ""] + ([f"- {c[0][1]}  \n  Sources: {', '.join(sorted({ref(it) for it in c}))}" for c in common] or ["- _None found across multiple videos._"])
    L += ["", "## Creator-specific explanations", ""]
    by_creator: dict[str, list] = {}
    for c in unique:
        by_creator.setdefault(c[0][2].video.channel.title if c[0][2].video.channel else "Unknown creator", []).append(c[0])
    for creator, its in by_creator.items():
        L.append(f"**{creator}**")
        L += [f"- {it[1]}  ({ref(it)})" for it in its[:6]]
    if not by_creator:
        L.append("- _None._")
    L += ["", "## New information", ""] + ([f"- {it[1]} ({ref(it)})" for it in new_items] or ["- _Nothing new beyond earlier notes._"])
    L += ["", "## Duplicates removed", "", f"- {deduped} near-duplicate point(s) merged."]
    L += ["", "## Conflicting claims", ""]
    L += [f"- ⚠️ {a[1]} ({ref(a)}) **vs** {b[1]} ({ref(b)})" for a, b in conflicts] or ["- _No numeric conflicts detected (heuristic)._"]
    L += ["", "## Examples / cases", ""] + ([f"- {it[1]} ({ref(it)})" for it in cases] or ["- _None._"])
    L += ["", "## Actionable guidance", ""] + ([f"- [ ] {a}" for a in actions] or ["- _None._"])
    L += ["", "## External checks", ""]
    for c in claims:
        L.append(f"- **{c.verdict}**: {c.text}")
        for e in c.evidence[:3]:
            L.append(f"  - {e.stance}: [{e.title or e.url}]({e.url})")
    if not claims:
        L.append("- _No claims have been cross-checked yet._")
    L += ["", "## References", ""] + [f"- [{n.video.title}]({video_url(n.video.youtube_video_id)})" for n in notes]
    stats = {"notes": len(notes), "points": total_points, "common": len(common), "unique": len(unique), "conflicts": len(conflicts), "deduped": deduped}
    s = Synthesis(user_id=user.id, topic=topic[:200], note_ids=[n.id for n in notes], markdown="\n".join(L) + "\n", stats=stats)
    db.add(s)
    db.add(KnowledgeChange(user_id=user.id, kind="added", detail=f"Synthesis created: {topic[:100]}"))
    db.commit()
    return s
