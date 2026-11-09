"""Parse user-supplied TXT / SRT / VTT into segments. Input is untrusted."""
import re
from dataclasses import dataclass

_TS = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
_TAG = re.compile(r"<[^>]+>")


@dataclass
class Segment:
    i: int
    start: float | None
    text: str


def _secs(m: re.Match) -> float:
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def parse_transcript(text: str, filename: str = "", max_segments: int = 20000) -> tuple[list[Segment], bool]:
    """Return (segments, has_timestamps)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lower = filename.lower()
    segs: list[Segment] = []
    if lower.endswith((".srt", ".vtt")) or "-->" in text[:2000]:
        for block in re.split(r"\n\s*\n", text):
            lines = [l for l in block.split("\n") if l.strip()]
            for k, line in enumerate(lines):
                if "-->" in line:
                    m = _TS.search(line)
                    body = _TAG.sub("", " ".join(lines[k + 1:])).strip()
                    if m and body:
                        segs.append(Segment(len(segs), _secs(m), body))
                    break
            if len(segs) > max_segments:
                raise ValueError("Too many segments")
        if segs:
            return segs, True
    # plain text: paragraphs, then sentence groups
    for para in re.split(r"\n\s*\n|\n", text):
        para = para.strip()
        if not para:
            continue
        sentences = re.split(r"(?<=[.!?。])\s+", para)
        for k in range(0, len(sentences), 3):
            chunk = " ".join(sentences[k:k + 3]).strip()
            if chunk:
                segs.append(Segment(len(segs), None, chunk))
        if len(segs) > max_segments:
            raise ValueError("Too many segments")
    return segs, False


def fmt_ts(sec: float | None) -> str:
    if sec is None:
        return ""
    sec = int(sec)
    return f"{sec // 3600:d}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:d}:{sec % 60:02d}"
