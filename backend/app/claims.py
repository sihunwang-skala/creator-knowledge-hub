"""Claim extraction + external cross-check.

Search providers are adapters. `FixtureSearchProvider` uses a small SYNTHETIC corpus (tests/demo);
`BraveSearchProvider` uses the Brave Search API when configured. The verdict logic is a transparent
heuristic judge (number/keyword agreement across *independent* origins) - not a guarantee of truth.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx

from .config import get_settings
from .db import utcnow
from .llm import tokens
from .transcript import Segment

NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_KINDS = [
    ("price", re.compile(r"[$€£₩]\s?\d|\b\d[\d,.]*\s?(dollars|euros|won|usd|krw)\b|per (month|year|seat)", re.I), 3),
    ("legal", re.compile(r"\b(law|regulation|act|gdpr|statute|ruling|compliance)\b", re.I), 3),
    ("research", re.compile(r"\b(study|studies|researchers?|paper|trial|survey|published)\b", re.I), 3),
    ("spec", re.compile(r"\b\d[\d,.]*\s?(gb|mb|tb|ms|hz|mah|jobs per second|requests per second|per second|terabytes?|gigabytes?)\b", re.I), 2),
    ("date", re.compile(r"\b(released|launched|announced|shipped|introduced)\b.*\b(19|20)\d\d\b|\bin (19|20)\d\d\b", re.I), 2),
    ("statistic", re.compile(r"\d+(\.\d+)?\s?(%|percent)|\b\d[\d,]*\s(users|customers|people|times)\b", re.I), 2),
]


@dataclass
class ClaimDraft:
    text: str
    kind: str
    priority: int
    t: float | None


def extract_claims(segments: list[Segment], max_claims: int = 12) -> list[ClaimDraft]:
    out, seen = [], set()
    for seg in segments:
        for sent in re.split(r"(?<=[.!?。])\s+", seg.text):
            sent = " ".join(sent.split())
            if not (20 <= len(sent) <= 300):
                continue
            for kind, rx, prio in _KINDS:
                if rx.search(sent) and (NUM_RE.search(sent) or kind in ("legal", "research")):
                    key = sent.lower()
                    if key not in seen:
                        seen.add(key)
                        out.append(ClaimDraft(sent, kind, prio, seg.start))
                    break
    out.sort(key=lambda c: -c.priority)
    return out[:max_claims]


# ---------- search adapters ----------
@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    published_at: datetime | None = None
    origin_key: str = ""  # canonical original; same value => not independent


class SearchProvider:
    name = "base"

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        raise NotImplementedError


_FIXTURE_CORPUS = [
    # SYNTHETIC documents for tests/demo about fictional "Acme Queue". Not real facts.
    ("https://docs.acme-queue.example/limits", "Acme Queue limits [synthetic]", "Acme Queue 2.0 processes up to 5000 jobs per second per node and retries failed jobs 4 times.", 20, "acme-docs"),
    ("https://bench.example.org/acme-queue-2", "Independent benchmark of Acme Queue 2.0 [synthetic]", "Our benchmark measured Acme Queue 2.0 at 5000 jobs per second on a single node.", 40, "bench-example"),
    ("https://news.example.net/acme-5000", "Acme Queue hits 5000 jobs per second [synthetic]", "Acme Queue 2.0 processes up to 5000 jobs per second per node and retries failed jobs 4 times.", 19, "acme-docs"),  # syndicated copy of docs
    ("https://pricing.acme-queue.example/", "Acme Queue pricing [synthetic]", "Acme Queue costs 29 dollars per month for the team plan. Updated pricing as of this year.", 5, "acme-pricing"),
    ("https://review.example.com/acme-price", "Acme Queue price review [synthetic]", "The team plan of Acme Queue is 29 dollars per month, up from the older price.", 12, "review-example"),
    ("https://study.example.edu/sleep", "Sleep consolidation study summary [synthetic]", "A synthetic study reported 18 percent better recall after a full night of sleep in 120 participants.", 60, "study-edu"),
]


class FixtureSearchProvider(SearchProvider):
    name = "fixture(synthetic)"

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        q = set(tokens(query))
        scored = []
        for url, title, text, age, origin in _FIXTURE_CORPUS:
            d = set(tokens(title + " " + text))
            if q and len(q & d) / len(q) >= 0.3:
                scored.append((len(q & d), SearchResult(url, title, text, utcnow() - timedelta(days=age), origin)))
        return [r for _, r in sorted(scored, key=lambda x: -x[0])[:limit]]


class BraveSearchProvider(SearchProvider):
    name = "brave"

    def __init__(self, key: str, transport: httpx.BaseTransport | None = None):
        self.key, self.transport = key, transport

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        with httpx.Client(timeout=15, transport=self.transport) as c:
            r = c.get("https://api.search.brave.com/res/v1/web/search", params={"q": query[:300], "count": limit},
                      headers={"X-Subscription-Token": self.key, "Accept": "application/json"})
        if r.status_code >= 400:
            raise RuntimeError(f"Search provider error {r.status_code}")
        out = []
        for it in r.json().get("web", {}).get("results", [])[:limit]:
            host = (urlparse(it.get("url", "")).hostname or "").removeprefix("www.")
            out.append(SearchResult(it["url"], it.get("title", ""), re.sub(r"<[^>]+>", "", it.get("description", "")), None, host))
        return out


def get_search_provider() -> SearchProvider:
    s = get_settings()
    if s.search_provider == "brave" and s.brave_api_key:
        return BraveSearchProvider(s.brave_api_key)
    return FixtureSearchProvider()


# ---------- evaluation ----------
def _nums(text: str) -> set[str]:
    return {n.replace(",", "").rstrip(".") for n in NUM_RE.findall(text)}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def collapse_origins(results: list[SearchResult]) -> dict[str, str]:
    """Map url -> origin group. A declared origin_key is trusted. Results without one are grouped by host,
    and merged into an earlier group when their snippets are near-identical (syndicated/copied text)."""
    groups: dict[str, str] = {}
    reps: list[tuple[str, set]] = []
    for r in results:
        toks = set(tokens(r.snippet))
        if r.origin_key:
            key = r.origin_key
        else:
            key = urlparse(r.url).hostname or r.url
            for rep_key, rep_toks in reps:
                if _jaccard(toks, rep_toks) >= 0.85:
                    key = rep_key
                    break
        reps.append((key, toks))
        groups[r.url] = key
    return groups


@dataclass
class Verdict:
    verdict: str
    rationale: str
    evidence: list[tuple[SearchResult, str, str]]  # (result, stance, origin_key)


def evaluate_claim(claim_text: str, results: list[SearchResult], video_published: datetime | None = None) -> Verdict:
    cnums = _nums(claim_text)
    ckw = set(tokens(NUM_RE.sub(" ", claim_text)))
    origins = collapse_origins(results)
    evidence, sup, con = [], set(), set()
    outdated = False
    for r in results:
        rel = len(ckw & set(tokens(r.snippet + " " + r.title))) / max(len(ckw), 1)
        snums = _nums(r.snippet)
        if rel < 0.35:
            stance = "neutral"
        elif cnums and cnums <= snums:
            stance = "supports"
            sup.add(origins[r.url])
        elif cnums and snums and not (cnums & snums):
            stance = "contradicts"
            con.add(origins[r.url])
            if r.published_at and video_published and r.published_at > video_published and re.search(r"\b(updated|now|as of|currently|older)\b", r.snippet, re.I):
                outdated = True
        else:
            stance = "neutral"
        evidence.append((r, stance, origins[r.url]))
    if not results:
        return Verdict("insufficient_evidence", "No search results were found. Absence of evidence is not treated as support.", evidence)
    if con and not sup:
        v = "outdated" if outdated else "contradicted"
        return Verdict(v, f"{len(con)} independent source(s) report different figures." + (" Newer sources indicate the claim is out of date." if outdated else ""), evidence)
    if sup and con:
        return Verdict("partially_supported", f"{len(sup)} independent source(s) support and {len(con)} contradict the claim.", evidence)
    if len(sup) >= 2:
        return Verdict("supported", f"{len(sup)} independent origins agree (syndicated copies counted once).", evidence)
    if len(sup) == 1:
        return Verdict("partially_supported", "Only one independent origin supports this claim (copies of the same source are not independent).", evidence)
    return Verdict("insufficient_evidence", "Search results did not contain matching figures; cannot confirm or refute.", evidence)
