#!/usr/bin/env python3
"""Minimal secret scanner for tracked + untracked-but-not-ignored files. Exit 1 on findings.
(Complements, not replaces, tools like gitleaks/trufflehog.)"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_\-]{35}",
    "anthropic_key": r"sk-ant-[A-Za-z0-9_\-]{20,}",
    "openai_style_key": r"sk-[A-Za-z0-9]{32,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "private_key": r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "slack_token": r"xox[baprs]-[A-Za-z0-9-]{10,}",
    "aws_access_key": r"AKIA[0-9A-Z]{16}",
    "ckh_user_token": r"ckh_[A-Za-z0-9_\-]{30,}",
    "assigned_secret": r"(?i)(api[_-]?key|secret|password)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
}
ALLOW_FILES = {"scripts/secret_scan.py", "backend/tests/test_policy_security.py", "backend/tests/test_units.py"}
files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.split("\n")
bad = []
for f in filter(None, files):
    if f in ALLOW_FILES or f.endswith((".jpg", ".png", ".lock", ".svg")) or "package-lock" in f:
        continue
    p = ROOT / f
    if not p.is_file() or p.stat().st_size > 2_000_000:
        continue
    text = p.read_text(errors="ignore")
    for name, rx in PATTERNS.items():
        for m in re.finditer(rx, text):
            bad.append(f"{f}: {name}: {m.group(0)[:8]}…")
    if f.startswith((".env",)) and f != ".env.example":
        bad.append(f"{f}: env file must not be committed")
if bad:
    print("Possible secrets found:\n" + "\n".join(bad))
    sys.exit(1)
print(f"secret scan: {len([f for f in files if f])} files clean")
