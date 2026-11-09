"""Full-text search over notes (SQLite FTS5; falls back to LIKE elsewhere)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import Note


def _is_sqlite(db: Session) -> bool:
    return db.get_bind().dialect.name == "sqlite"


def ensure_fts(db: Session) -> None:
    if not _is_sqlite(db):
        return
    try:
        db.execute(text("CREATE VIRTUAL TABLE IF NOT EXISTS note_fts USING fts5(title, body, tags, note_id UNINDEXED, user_id UNINDEXED)"))
        db.commit()
    except Exception:
        db.rollback()


def note_text(n: Note) -> str:
    parts = [p["text"] for p in n.points] + list(n.action_items) + [g.get("term", "") + " " + g.get("explanation", "") for g in n.glossary]
    parts.append(n.user_notes or "")
    if n.edited_md:
        parts.append(n.edited_md)
    return "\n".join(parts)


def index_note(db: Session, n: Note) -> None:
    if not _is_sqlite(db):
        return
    try:
        db.execute(text("DELETE FROM note_fts WHERE note_id = :i"), {"i": n.id})
        db.execute(text("INSERT INTO note_fts(title, body, tags, note_id, user_id) VALUES (:t, :b, :g, :i, :u)"),
                   {"t": n.title, "b": note_text(n), "g": " ".join(n.tags), "i": n.id, "u": n.user_id})
    except Exception:
        pass


def unindex_user(db: Session, user_id: int) -> None:
    if _is_sqlite(db):
        try:
            db.execute(text("DELETE FROM note_fts WHERE user_id = :u"), {"u": user_id})
        except Exception:
            pass


def _fts_query(q: str) -> str:
    toks = [t for t in "".join(c if c.isalnum() else " " for c in q).split() if t]
    return " ".join(f'"{t}"*' for t in toks)  # quoted => user input cannot inject FTS syntax


def search_notes(db: Session, user_id: int, q: str, limit: int = 50) -> list[int]:
    q = (q or "").strip()
    if not q:
        return []
    if _is_sqlite(db):
        fq = _fts_query(q)
        if not fq:
            return []
        try:
            rows = db.execute(text("SELECT note_id FROM note_fts WHERE note_fts MATCH :q AND user_id = :u ORDER BY rank LIMIT :l"),
                              {"q": fq, "u": user_id, "l": limit}).all()
            return [r[0] for r in rows]
        except Exception:
            pass
    like = f"%{q}%"
    notes = db.query(Note).filter(Note.user_id == user_id, Note.title.ilike(like)).limit(limit).all()
    return [n.id for n in notes]
