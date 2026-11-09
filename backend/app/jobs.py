"""DB-backed job queue: idempotent enqueue, atomic claim, stale-lock recovery, exponential backoff."""
import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import SessionLocal, utcnow
from .models import Job, Subscription, User
from .youtube import QuotaExceeded

log = logging.getLogger("ckh.jobs")
LOCK_TIMEOUT = timedelta(minutes=10)
BASE_BACKOFF = 30  # seconds
HANDLERS: dict[str, Callable[[Session, dict], None]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def enqueue(db: Session, kind: str, payload: dict, dedupe_key: str, run_after=None, max_attempts: int = 4) -> Job:
    """Idempotent: the same dedupe_key never creates a second job (even across restarts/races)."""
    existing = db.query(Job).filter_by(dedupe_key=dedupe_key).first()
    if existing:
        return existing
    job = Job(kind=kind, payload=payload, dedupe_key=dedupe_key, run_after=run_after or utcnow(), max_attempts=max_attempts)
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(Job).filter_by(dedupe_key=dedupe_key).one()
    return job


def recover_stale(db: Session) -> int:
    res = db.execute(update(Job).where(Job.status == "running", Job.locked_at < utcnow() - LOCK_TIMEOUT)
                     .values(status="queued", locked_at=None))
    db.commit()
    return res.rowcount or 0


def run_next(db: Session) -> Job | None:
    recover_stale(db)
    candidates = db.query(Job.id).filter(Job.status == "queued", Job.run_after <= utcnow()).order_by(Job.run_after, Job.id).limit(5).all()
    for (jid,) in candidates:
        # atomic claim: only one worker flips queued -> running
        res = db.execute(update(Job).where(Job.id == jid, Job.status == "queued").values(status="running", locked_at=utcnow()))
        db.commit()
        if res.rowcount != 1:
            continue
        job = db.get(Job, jid)
        job.attempts += 1
        db.commit()  # persist the attempt before running, so a rollback/crash can't lose it
        try:
            HANDLERS[job.kind](db, job.payload)
            job.status, job.error = "done", ""
        except QuotaExceeded as e:  # not retryable today; try again after the quota day rolls
            job.status, job.run_after, job.error = "queued", utcnow() + timedelta(hours=1), str(e)[:300]
        except Exception as e:  # noqa: BLE001
            db.rollback()
            job = db.get(Job, jid)
            job.error = f"{type(e).__name__}"[:300]
            if job.attempts >= job.max_attempts:
                job.status = "failed"
            else:
                job.status, job.run_after = "queued", utcnow() + timedelta(seconds=BASE_BACKOFF * 2 ** (job.attempts - 1))
            log.warning("job %s failed (%s), attempt %s", job.id, job.error, job.attempts)
        job.locked_at = None
        db.commit()
        return job
    return None


def run_pending(db: Session, limit: int = 50) -> int:
    n = 0
    while n < limit and run_next(db):
        n += 1
    return n


# ---------- handlers ----------
@handler("poll_channel")
def _poll(db: Session, payload: dict) -> None:
    from .services import poll_channel
    poll_channel(db, payload["channel_id"])


@handler("generate_digest")
def _digest(db: Session, payload: dict) -> None:
    from .digest import generate_digest
    user = db.get(User, payload["user_id"])
    if user and user.digest_frequency != "off":
        generate_digest(db, user)


@handler("purge_expired")
def _purge(db: Session, payload: dict) -> None:
    from .services import purge_expired
    purge_expired(db)


def schedule_tick(db: Session) -> dict:
    """Enqueue due work. Safe to call as often as you like - dedupe keys are time-bucketed."""
    now = utcnow()
    hour, day = now.strftime("%Y%m%d%H"), now.strftime("%Y%m%d")
    polls = 0
    for ch_id in {s.channel_id for s in db.query(Subscription).filter(Subscription.auto_process == True)}:  # noqa: E712
        enqueue(db, "poll_channel", {"channel_id": ch_id}, f"poll:{ch_id}:{hour}")
        polls += 1
    for u in db.query(User).filter(User.digest_frequency != "off"):
        bucket = day if u.digest_frequency == "daily" else now.strftime("%G-W%V")
        enqueue(db, "generate_digest", {"user_id": u.id}, f"digest:{u.id}:{u.digest_frequency}:{bucket}")
    enqueue(db, "purge_expired", {}, f"purge:{day}")
    return {"polls": polls}


async def scheduler_loop(interval_sec: int = 900):
    import asyncio
    while True:
        try:
            with SessionLocal() as db:
                schedule_tick(db)
                await asyncio.to_thread(run_pending, db)
        except Exception:  # noqa: BLE001
            log.exception("scheduler tick failed")
        await asyncio.sleep(interval_sec)
