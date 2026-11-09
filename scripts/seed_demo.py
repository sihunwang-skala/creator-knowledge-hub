#!/usr/bin/env python3
"""Populate a running local server with a demo profile using the synthetic samples/ only.

Usage:  python scripts/seed_demo.py [http://127.0.0.1:8000]
Prints the access token; paste it in the browser console:  localStorage.setItem("ckh-token", "<token>")
"""
import sys
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/") + "/api"
SAMPLES = Path(__file__).resolve().parents[1] / "samples"

c = httpx.Client(base_url=BASE, timeout=30)
tok = c.post("/users", json={"name": "Demo user"}).json()["token"]
c.headers["Authorization"] = f"Bearer {tok}"
c.patch("/me", json={"role_profile": "software engineer", "interests": ["queue", "pricing"], "digest_frequency": "weekly"})
for ch in ("@syntheticdevlab", "@demofoundershow", "@samplesciencehour"):
    c.post("/creators", json={"channel": ch}).raise_for_status()

note_ids = []
for vid, fname, style in (("devDemo0001", "devDemo0001.srt", "practical"), ("devDemo0002", "devDemo0002.txt", "tips"), ("fndDemo0001", "fndDemo0001.txt", "arguments")):
    uv = c.post("/videos/quick-add", json={"url": f"https://youtu.be/{vid}"}).json()
    data = {"acquisition_method": "user_upload", "license": "self-authored synthetic sample", "owner": "creator-knowledge-hub",
            "rights_attested": "true", "permission_evidence": "Synthetic text written for this repository"}
    c.post(f"/videos/{uv['id']}/sources/upload", files={"file": (fname, (SAMPLES / fname).read_bytes())}, data=data).raise_for_status()
    note = c.post(f"/videos/{uv['id']}/analyze", json={"style": style}).json()
    c.post(f"/notes/{note['id']}/crosscheck", params={"min_priority": 1})
    note_ids.append(note["id"])
c.post("/collections", json={"name": "Backend ideas"})
c.post("/synthesis", json={"topic": "Acme Queue and job design", "note_ids": note_ids})
c.post("/digests", params={"frequency": "weekly"})
print(tok)
