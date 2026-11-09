import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp(prefix="ckh-test-")
os.environ["CKH_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
for k in ("CKH_YOUTUBE_API_KEY", "CKH_ANTHROPIC_API_KEY", "CKH_BRAVE_API_KEY"):
    os.environ.pop(k, None)
os.environ["CKH_LLM_PROVIDER"] = "local"
os.environ["CKH_SEARCH_PROVIDER"] = "fixture"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.deps import reset_rate_limits
from app.main import app
from app.search import ensure_fts

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture(autouse=True)
def fresh_db():
    with engine.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS note_fts"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        ensure_fts(db)
    reset_rate_limits()
    from app.youtube import DemoYouTubeProvider
    DemoYouTubeProvider.extra_videos = {}
    yield


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


@pytest.fixture
def client():
    return TestClient(app)


class Api:
    """Tiny helper around a signed-up user."""

    def __init__(self, client, name="alice"):
        self.c = client
        r = client.post("/api/users", json={"name": name})
        assert r.status_code == 200, r.text
        self.token = r.json()["token"]
        self.h = {"Authorization": f"Bearer {self.token}"}

    def get(self, p, **kw):
        return self.c.get("/api" + p, headers=self.h, **kw)

    def post(self, p, **kw):
        return self.c.post("/api" + p, headers=self.h, **kw)

    def patch(self, p, **kw):
        return self.c.patch("/api" + p, headers=self.h, **kw)

    def delete(self, p, **kw):
        return self.c.delete("/api" + p, headers=self.h, **kw)

    def upload(self, uvid, sample, **form):
        data = (SAMPLES / sample).read_bytes()
        base = {"acquisition_method": "user_upload", "license": "self-authored synthetic sample", "owner": "project",
                "rights_attested": "true", "permission_evidence": "Synthetic sample written for this repo"}
        base.update(form)
        return self.post(f"/videos/{uvid}/sources/upload", files={"file": (sample, data, "text/plain")}, data=base)


@pytest.fixture
def alice(client):
    return Api(client, "alice")


@pytest.fixture
def bob(client):
    return Api(client, "bob")
