import { useState } from "react";
import { api, download } from "../api";
import type { Claim, Note } from "../types";
import { Badge, Empty, ErrorBox, Markdown, PageHeader, Spinner, useAction, useLoad } from "../ui";
import { VERDICT_LABEL, formatTimestamp } from "../utils";

export default function Library() {
  const params = new URLSearchParams(location.hash.split("?")[1] ?? "");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [tag, setTag] = useState(params.get("tag") ?? "");
  const [fav, setFav] = useState(false);
  const notes = useLoad(() => api<Note[]>(`/notes?q=${encodeURIComponent(q)}&tag=${encodeURIComponent(tag)}&favorite=${fav}`), [q, tag, fav]);
  return (
    <>
      <PageHeader title="My Knowledge Library" sub="Everything you've saved, searchable.">
        <button className="btn" onClick={async () => download("library.md", await api("/export/library.md", { text: true }))}>Export all (Markdown)</button>
      </PageHeader>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input type="search" aria-label="Search notes" className="input !w-auto min-w-0 flex-1" placeholder="Search notes…" value={q} onChange={(e) => setQ(e.target.value)} />
        {tag && <button className="btn" onClick={() => setTag("")}>Tag: {tag} ✕</button>}
        <label className="flex items-center gap-1.5 text-sm"><input type="checkbox" checked={fav} onChange={(e) => setFav(e.target.checked)} /> Favorites</label>
      </div>
      {notes.loading ? <Spinner /> : notes.error ? <ErrorBox error={notes.error} onRetry={notes.reload} /> :
        notes.data!.length === 0 ? <Empty title={q || tag || fav ? "No matching notes" : "Your library is empty"}>{q || tag || fav ? "Try a different search." : <>Add a video, attach a permitted source and run analysis. <a className="underline" href="#/">Go to feed</a></>}</Empty> : (
          <ul className="space-y-3">{notes.data!.map((n) => (
            <li key={n.id} className="card">
              <a href={`#/note/${n.id}`} className="font-medium hover:underline">{n.favorite && "★ "}{n.title}</a>
              <p className="text-sm text-slate-500">{n.video.channel} · {n.style} · v{n.version}</p>
              {n.preview?.map((p, i) => <p key={i} className="mt-1 text-sm">• {p}</p>)}
              <div className="mt-2 flex flex-wrap gap-1.5">{n.tags.map((t) => <button key={t} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800" onClick={() => setTag(t)}>{t}</button>)}{n.duplicate_of && <Badge tone="amber">Possible duplicate of #{n.duplicate_of}</Badge>}</div>
            </li>))}</ul>
        )}
    </>
  );
}

function ClaimCard({ c, onChecked }: { c: Claim; onChecked: () => void }) {
  const act = useAction();
  const v = VERDICT_LABEL[c.verdict] ?? VERDICT_LABEL.unchecked;
  return (
    <li className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2"><Badge tone={v.tone}>{v.text}</Badge><Badge>{c.kind}</Badge></div>
      <p className="mt-1">{c.text}</p>
      {c.rationale && <p className="mt-1 text-slate-500">{c.rationale}</p>}
      {c.evidence.length > 0 && <ul className="mt-2 space-y-1">{c.evidence.map((e, i) => <li key={i}><Badge tone={e.stance === "supports" ? "green" : e.stance === "contradicts" ? "red" : "gray"}>{e.stance}</Badge>{" "}<a className="underline" href={e.url} target="_blank" rel="noopener noreferrer">{e.title || e.url}</a> <span className="text-xs text-slate-500">origin: {e.origin} · retrieved {e.retrieved_at.slice(0, 10)}</span></li>)}</ul>}
      {act.error != null && <ErrorBox error={act.error} />}
      <button className="btn mt-2" disabled={act.busy} onClick={() => act.run(async () => { await api(`/claims/${c.id}/check`, { method: "POST" }); onChecked(); })}>{c.verdict === "unchecked" ? "Cross-check" : "Re-check"}</button>
    </li>
  );
}

export function NoteView({ id }: { id: number }) {
  const n = useLoad(() => api<Note>(`/notes/${id}`), [id]);
  const related = useLoad(() => api<Note[]>(`/notes/${id}/related`), [id]);
  const revs = useLoad(() => api<any[]>(`/notes/${id}/revisions`), [id]);
  const act = useAction();
  const [edit, setEdit] = useState<string | null>(null);
  const [mine, setMine] = useState<string | null>(null);
  if (n.loading) return <Spinner />;
  if (n.error) return <ErrorBox error={n.error} onRetry={n.reload} />;
  const note = n.data!;
  const patch = (body: object) => act.run(async () => { await api(`/notes/${id}`, { method: "PATCH", body }); setEdit(null); setMine(null); n.reload(); });
  const vid = note.video.youtube_video_id;
  return (
    <>
      <PageHeader title={note.title} sub={`${note.video.title} · ${note.video.channel ?? ""}`}>
        <button className="btn" aria-pressed={note.favorite} onClick={() => patch({ favorite: !note.favorite })}>{note.favorite ? "★ Favorite" : "☆ Favorite"}</button>
        <button className="btn" onClick={async () => download(`note-${id}.md`, await api(`/notes/${id}/export.md`, { text: true }))}>Export Markdown</button>
        <button className="btn" disabled={act.busy} onClick={() => act.run(async () => { await api(`/notes/${id}/regenerate`, { method: "POST" }); n.reload(); revs.reload(); })}>Regenerate</button>
      </PageHeader>
      <p className="mb-3 rounded-md bg-slate-100 p-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">AI-generated by <strong>{note.provider}</strong> / {note.model} (prompt {note.prompt_version}). Not guaranteed accurate — verify against the original video. “Source” points are tied to your attached transcript; “AI-added” points are the model’s own words.</p>
      {act.error != null && <ErrorBox error={act.error} />}
      <section className="card mb-4" aria-labelledby="kp"><h2 id="kp" className="mb-2 font-semibold">Key points</h2>
        {note.edited_md != null && edit === null && <div className="mb-3 rounded bg-indigo-50 p-3 dark:bg-indigo-950"><p className="mb-1 text-xs font-medium">Your edited version</p><Markdown text={note.edited_md} /></div>}
        <ul className="space-y-2">{note.points.map((p, i) => (
          <li key={i} className="flex gap-2 text-sm"><Badge tone={p.kind === "source" ? "blue" : "amber"}>{p.kind === "source" ? "Source" : "AI-added"}</Badge>
            <span>{p.text} {p.t != null && <a className="text-xs text-indigo-700 underline dark:text-indigo-300" href={`https://www.youtube.com/watch?v=${vid}&t=${Math.floor(p.t)}s`} target="_blank" rel="noopener noreferrer">{formatTimestamp(p.t)}</a>}</span></li>))}</ul>
        {note.action_items.length > 0 && <><h3 className="mb-1 mt-4 text-sm font-semibold">Action items</h3><ul className="space-y-1 text-sm">{note.action_items.map((a, i) => <li key={i}>☐ {a}</li>)}</ul></>}
        {note.glossary.length > 0 && <><h3 className="mb-1 mt-4 text-sm font-semibold">Glossary</h3><dl className="text-sm">{note.glossary.map((g, i) => <div key={i}><dt className="inline font-medium">{g.term}: </dt><dd className="inline">{g.explanation}</dd></div>)}</dl></>}
      </section>
      <section className="card mb-4" aria-labelledby="ed"><h2 id="ed" className="mb-2 font-semibold">Edit & annotate</h2>
        <label className="label" htmlFor="em">Replace the AI text with your own version (Markdown)</label>
        <textarea id="em" className="input min-h-28" value={edit ?? note.edited_md ?? ""} onChange={(e) => setEdit(e.target.value)} />
        <button className="btn mt-2" disabled={edit === null || act.busy} onClick={() => patch({ edited_md: edit })}>Save my version</button>
        <label className="label mt-4" htmlFor="mn">My notes</label>
        <textarea id="mn" className="input min-h-20" value={mine ?? note.user_notes} onChange={(e) => setMine(e.target.value)} />
        <button className="btn mt-2" disabled={mine === null || act.busy} onClick={() => patch({ user_notes: mine })}>Save notes</button>
        <p className="mt-3 text-xs text-slate-500">Tags: {note.tags.join(", ") || "—"}</p>
      </section>
      <section className="card mb-4" aria-labelledby="cl"><h2 id="cl" className="mb-2 font-semibold">Claims & cross-check</h2>
        {note.claims!.length === 0 ? <p className="text-sm text-slate-500">No checkable factual claims were found in this source.</p> : <ul className="space-y-2">{note.claims!.map((c) => <ClaimCard key={c.id} c={c} onChecked={n.reload} />)}</ul>}
      </section>
      {(related.data?.length ?? 0) > 0 && <section className="card mb-4"><h2 className="mb-2 font-semibold">Related notes</h2><ul className="space-y-1 text-sm">{related.data!.map((r: any) => <li key={r.id}><a className="underline" href={`#/note/${r.id}`}>{r.title}</a> <span className="text-slate-500">shared: {r.shared_tags.join(", ")}</span></li>)}</ul></section>}
      {(revs.data?.length ?? 0) > 0 && <section className="card"><h2 className="mb-2 font-semibold">History</h2><ul className="space-y-1 text-sm text-slate-600 dark:text-slate-400">{revs.data!.map((r: any) => <li key={r.version}>v{r.version} — {r.reason} · {r.created_at.slice(0, 16).replace("T", " ")} · {r.points.length} points</li>)}</ul></section>}
    </>
  );
}
