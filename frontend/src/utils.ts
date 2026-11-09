export function formatDuration(sec: number): string {
  if (!sec) return "–";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}

export function formatTimestamp(sec: number | null): string {
  return sec == null ? "" : formatDuration(Math.max(0, Math.floor(sec))).replace("–", "0:00");
}

export const ANALYSIS_LABEL: Record<string, { text: string; tone: "gray" | "green" | "amber" | "red" | "blue" }> = {
  not_started: { text: "Ready to analyze", tone: "blue" },
  source_required: { text: "Source required", tone: "amber" },
  analysis_unavailable: { text: "Analysis unavailable", tone: "red" },
  processing: { text: "Processing", tone: "blue" },
  done: { text: "Analyzed", tone: "green" },
  blocked: { text: "Permission required", tone: "red" },
};

export const VERDICT_LABEL: Record<string, { text: string; tone: "gray" | "green" | "amber" | "red" | "blue" }> = {
  unchecked: { text: "Unchecked", tone: "gray" },
  supported: { text: "Supported", tone: "green" },
  partially_supported: { text: "Partially supported", tone: "amber" },
  contradicted: { text: "Contradicted", tone: "red" },
  insufficient_evidence: { text: "Insufficient evidence", tone: "gray" },
  outdated: { text: "Outdated", tone: "amber" },
};

export function timeAgo(iso: string | null, now = Date.now()): string {
  if (!iso) return "never";
  const d = (now - new Date(iso).getTime()) / 1000;
  if (d < 90) return "just now";
  if (d < 5400) return `${Math.round(d / 60)} min ago`;
  if (d < 129600) return `${Math.round(d / 3600)} h ago`;
  return `${Math.round(d / 86400)} d ago`;
}

export function parseVideoRef(input: string): string | null {
  const s = input.trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(s)) return s;
  try {
    const u = new URL(s.includes("://") ? s : `https://${s}`);
    const host = u.hostname.replace(/^www\./, "");
    if (!["youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"].includes(host)) return null;
    const id = host === "youtu.be" ? u.pathname.slice(1).split("/")[0] : u.pathname === "/watch" ? u.searchParams.get("v") ?? "" : (u.pathname.match(/^\/(?:shorts|embed|live|v)\/([^/]+)/)?.[1] ?? "");
    return /^[A-Za-z0-9_-]{11}$/.test(id) ? id : null;
  } catch { return null; }
}
