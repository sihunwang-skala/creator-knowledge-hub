import { useState } from "react";
import { api } from "../api";
import type { Me, Source, UserVideo } from "../types";
import { Badge, ErrorBox, PageHeader, Spinner, useAction, useLoad } from "../ui";
import { ANALYSIS_LABEL, formatDuration } from "../utils";

const METHODS = [
  ["user_upload", "My own / licensed file (private use)"], ["creator_provided", "Provided by the creator"],
  ["licensed_distribution", "Separately licensed transcript"], ["podcast_rss", "Podcast RSS transcript (licensed)"],
];
const TONE = { approved: "green", pending: "amber", denied: "red" } as const;

function SourceForm({ uvid, onDone }: { uvid: number; onDone: () => void }) {
  const [tab, setTab] = useState<"upload" | "note" | "web">("upload");
  const [f, setF] = useState({ method: "user_upload", license: "", owner: "", url: "", evidence: "", attested: false, text: "" });
  const [file, setFile] = useState<File | null>(null);
  const act = useAction();
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    act.run(async () => {
      if (tab === "note") await api(`/videos/${uvid}/sources/note`, { body: { text: f.text } });
      else if (tab === "web") await api(`/videos/${uvid}/sources/web`, { body: { url: f.url, license: f.license, owner: f.owner, permission_evidence: f.evidence } });
      else {
        const fd = new FormData();
        fd.append("file", file!);
        fd.append("acquisition_method", f.method); fd.append("license", f.license); fd.append("owner", f.owner);
        fd.append("source_url", f.url); fd.append("permission_evidence", f.evidence); fd.append("rights_attested", String(f.attested));
        await api(`/videos/${uvid}/sources/upload`, { form: fd });
      }
      onDone();
    });
  };
  return (
    <form onSubmit={submit} className="space-y-3">
      <div role="tablist" aria-label="Source type" className="flex gap-1">
        {([["upload", "Upload TXT/SRT/VTT"], ["note", "Write my own notes"], ["web", "Licensed web page"]] as const).map(([k, l]) => (
          <button type="button" role="tab" key={k} aria-selected={tab === k} className={`btn ${tab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "upload" && (<>
        <div><label className="label" htmlFor="f">File (.txt, .srt, .vtt — max 1 MB)</label><input id="f" type="file" accept=".txt,.srt,.vtt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></div>
        <div><label className="label" htmlFor="m">How did you obtain it?</label><select id="m" className="input" value={f.method} onChange={(e) => set("method", e.target.value)}>{METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      </>)}
      {tab === "note" && <div><label className="label" htmlFor="tx">Your notes about the video (analysed as your own writing)</label><textarea id="tx" className="input min-h-32" value={f.text} onChange={(e) => set("text", e.target.value)} /></div>}
      {tab === "web" && <div><label className="label" htmlFor="wu">https URL of the licensed document</label><input id="wu" className="input" value={f.url} onChange={(e) => set("url", e.target.value)} placeholder="https://…" /></div>}
      {tab !== "note" && (<>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label" htmlFor="lic">License (e.g. CC-BY-4.0, “own content”)</label><input id="lic" className="input" value={f.license} onChange={(e) => set("license", e.target.value)} /></div>
          <div><label className="label" htmlFor="ow">Owner / creator</label><input id="ow" className="input" value={f.owner} onChange={(e) => set("owner", e.target.value)} /></div>
        </div>
        {tab === "upload" && <div><label className="label" htmlFor="su">Source URL (optional, for citation)</label><input id="su" className="input" value={f.url} onChange={(e) => set("url", e.target.value)} /></div>}
        <div><label className="label" htmlFor="ev">Permission evidence (link or description of your right to use this text)</label><textarea id="ev" className="input" value={f.evidence} onChange={(e) => set("evidence", e.target.value)} /></div>
      </>)}
      {tab === "upload" && (
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={f.attested} onChange={(e) => set("attested", e.target.checked)} />
          <span>I confirm I have the right to process this file. <span className="text-slate-500">This is recorded, but it does not verify your rights or YouTube’s terms; the file stays private and is never redistributed.</span></span></label>
      )}
      {act.error != null && <ErrorBox error={act.error} />}
      <button className="btn btn-primary" disabled={act.busy || (tab === "upload" && !file) || (tab === "note" && !f.text.trim()) || (tab === "web" && !f.url)}>{act.busy ? "Checking permission…" : "Add source"}</button>
    </form>
  );
}

function SourceRow({ s, onChange }: { s: Source; onChange: () => void }) {
  const [ev, setEv] = useState("");
  const act = useAction();
  return (
    <li className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
      <div className="flex flex-wrap items-center gap-2"><Badge tone={TONE[s.status]}>{s.status}</Badge><span className="font-medium">{s.acquisition_method}</span><span className="text-slate-500">license: {s.license || "—"} · scope: {s.permission_scope || "—"}</span></div>
      <p className="mt-1 text-slate-600 dark:text-slate-400">{s.policy_reason}</p>
      {s.injection_flags.length > 0 && <p className="mt-1 text-amber-700 dark:text-amber-300">Contains instruction-like text (treated as data only): {s.injection_flags.join("; ")}</p>}
      <p className="mt-1 text-xs text-slate-500">Retained {s.retention_days} days · {s.has_timestamps ? "timestamps available" : "no timestamps"} · {s.content_available ? "text stored privately" : "text removed"}</p>
      {s.status === "pending" && (
        <div className="mt-2 flex gap-2"><input className="input" aria-label="Permission evidence" value={ev} onChange={(e) => setEv(e.target.value)} placeholder="Add evidence of your right to use this text" />
          <button className="btn" disabled={act.busy || ev.length < 10} onClick={() => act.run(async () => { await api(`/sources/${s.id}/reevaluate`, { body: { permission_evidence: ev } }); onChange(); })}>Re-check</button></div>
      )}
      <button className="btn btn-danger mt-2" onClick={() => act.run(async () => { await api(`/sources/${s.id}`, { method: "DELETE" }); onChange(); })}>Delete source</button>
    </li>
  );
}

export default function VideoDetail({ id, me }: { id: number; me: Me | null }) {
  const d = useLoad(() => api<UserVideo>(`/videos/${id}`), [id]);
  const [style, setStyle] = useState("");
  const [player, setPlayer] = useState(false);
  const act = useAction();
  if (d.loading) return <Spinner />;
  if (d.error) return <ErrorBox error={d.error} onRetry={d.reload} />;
  const u = d.data!, v = u.video, st = ANALYSIS_LABEL[u.analysis_status] ?? ANALYSIS_LABEL.not_started;
  const approved = u.sources!.filter((s) => s.status === "approved");
  const analyze = () => act.run(async () => { const n = await api("/videos/" + id + "/analyze", { body: { style: style || me?.default_style || "brief" } }); location.hash = `#/note/${n.id}`; });
  return (
    <>
      <PageHeader title={v.title} sub={`${v.channel ?? "Unknown channel"} · ${formatDuration(v.duration_sec)}`}>
        <a className="btn" href={v.url} target="_blank" rel="noopener noreferrer">Open on YouTube</a>
        <button className="btn" onClick={() => setPlayer(!player)}>{player ? "Hide player" : "Show player"}</button>
      </PageHeader>
      <div className="mb-3 flex flex-wrap gap-1.5"><Badge tone={st.tone}>{st.text}</Badge>{v.is_demo && <Badge tone="amber">Demo data</Badge>}{!v.metadata_available && <Badge tone="red">Metadata unavailable</Badge>}</div>
      {player && <iframe className="mb-4 aspect-video w-full rounded-lg" src={`https://www.youtube-nocookie.com/embed/${v.youtube_video_id}`} title={v.title} allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />}
      {u.analysis_status === "source_required" && (
        <div role="status" className="mb-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <strong>Source required.</strong> This video is saved as a bookmark. We never summarise from the title or description, and we don’t fetch YouTube captions. Attach a transcript you’re allowed to use to enable AI notes.
        </div>
      )}
      <section className="card mb-5" aria-labelledby="an"><h2 id="an" className="mb-3 font-semibold">AI notes</h2>
        <div className="flex flex-wrap items-end gap-2">
          <div><label className="label" htmlFor="st">Style</label><select id="st" className="input" value={style || me?.default_style || "brief"} onChange={(e) => setStyle(e.target.value)}>{Object.entries(me?.styles ?? {}).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <button className="btn btn-primary" disabled={act.busy || approved.length === 0} onClick={analyze}>{act.busy ? "Analyzing…" : "Analyze with permitted source"}</button>
        </div>
        {approved.length === 0 && <p className="mt-2 text-sm text-slate-500">Analysis is disabled until at least one source is approved.</p>}
        {me?.llm_provider !== "local" && !me?.llm_consent && <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">An external LLM is configured: enable consent in <a className="underline" href="#/settings">Settings</a> first.</p>}
        {act.error != null && <div className="mt-3"><ErrorBox error={act.error} /></div>}
        {u.notes!.length > 0 && <ul className="mt-4 space-y-1">{u.notes!.map((n) => <li key={n.id}><a className="underline" href={`#/note/${n.id}`}>{n.title}</a> <span className="text-xs text-slate-500">v{n.version} · {n.provider}</span></li>)}</ul>}
      </section>
      <section className="card mb-5" aria-labelledby="src"><h2 id="src" className="mb-3 font-semibold">Sources & permissions</h2>
        {u.sources!.length === 0 ? <p className="mb-3 text-sm text-slate-500">No sources attached.</p> : <ul className="mb-4 space-y-2">{u.sources!.map((s) => <SourceRow key={s.id} s={s} onChange={d.reload} />)}</ul>}
        <SourceForm uvid={id} onDone={d.reload} />
      </section>
    </>
  );
}
