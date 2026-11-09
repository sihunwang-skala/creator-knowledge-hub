import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User
from .security import hash_token

_hits: dict[str, deque] = defaultdict(deque)


def _limit(key: str, limit: int) -> None:
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Rate limit exceeded. Try again in a minute.")
    q.append(now)


def reset_rate_limits() -> None:
    _hits.clear()


def current_user(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    token = authorization.removeprefix("Bearer ").strip()
    user = db.query(User).filter_by(token_hash=hash_token(token)).first() if token else None
    if not user:
        raise HTTPException(401, "Missing or invalid token")
    _limit(f"u{user.id}", get_settings().rate_limit_per_minute)
    return user


def expensive(user: User = Depends(current_user)) -> User:
    """Stricter limit for routes that hit paid/quota-limited services."""
    _limit(f"x{user.id}", get_settings().expensive_rate_limit_per_minute)
    return user


def ip_limit(request: Request) -> None:
    _limit(f"ip{request.client.host if request.client else '?'}", 30)
