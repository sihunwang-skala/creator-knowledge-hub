import { useState } from "react";
import { api } from "../api";
import type { Creator } from "../types";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, useAction, useLoad } from "../ui";
import { timeAgo } from "../utils";

export default function Creators({ demo }: { demo?: boolean }) {
  const list = useLoad(() => api<Creator[]>("/creators"));
  const [q, setQ] = useState("");
  const [results, setResults] = useState<any[] | null>(null);
  const act = useAction();

  const add = (channel: string) => act.run(async () => { await api("/creators", { body: { channel } }); setQ(""); setResults(null); list.reload(); });
  const patch = (id: number, body: object) => act.run(async () => { await api(`/creators/${id}`, { method: "PATCH", body }); list.reload(); });
  const search = () => act.run(async () => setResults(await api(`/creators/search?q=${encodeURIComponent(q)}`)));

  return (
    <>
      <PageHeader title="My Creators" sub="Channels you follow. Videos are discovered with the official YouTube Data API." />
      <form className="card mb-5 space-y-3" onSubmit={(e) => { e.preventDefault(); add(q); }}>
        <label className="label" htmlFor="ch">Channel URL, @handle, or channel ID</label>
        <div className="flex flex-wrap gap-2">
          <input id="ch" className="input !w-auto min-w-0 flex-1" value={q} onChange={(e) => setQ(e.target.value)} placeholder="https://youtube.com/@handle" />
          <button className="btn btn-primary" disabled={act.busy || !q.trim()}>Follow</button>
          <button type="button" className="btn" disabled={act.busy || !q.trim()} onClick={search}>Search channels</button>
        </div>
        {demo && <p className="text-xs text-slate-500">Demo mode — try: {["@syntheticdevlab", "@demofoundershow", "@samplesciencehour"].map((h) => <button type="button" key={h} className="mr-2 underline" onClick={() => add(h)}>{h}</button>)}</p>}
        {act.error != null && <ErrorBox error={act.error} />}
        {results && (results.length === 0 ? <p className="text-sm text-slate-500">No channels found.</p> : (
          <ul className="divide-y divide-slate-200 dark:divide-slate-800">
            {results.map((r) => <li key={r.youtube_channel_id} className="flex items-center justify-between gap-3 py-2 text-sm"><span>{r.title} <span className="text-slate-500">{r.handle}</span></span><button type="button" className="btn" onClick={() => add(r.youtube_channel_id)}>Follow</button></li>)}
          </ul>
        ))}
      </form>
      {list.loading ? <Spinner /> : list.error ? <ErrorBox error={list.error} onRetry={list.reload} /> :
        list.data!.length === 0 ? <Empty title="You are not following anyone yet">Add a channel above to start building your feed.</Empty> : (
          <ul className="space-y-3">
            {list.data!.map((c) => (
              <li key={c.id} className="card">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="font-medium">{c.title} {c.is_demo && <Badge tone="amber">Demo</Badge>}</p><p className="text-sm text-slate-500">{c.handle} · checked {timeAgo(c.last_polled_at)}</p></div>
                  <div className="flex flex-wrap items-center gap-2 text-sm">
                    <label className="flex items-center gap-1.5"><input type="checkbox" checked={c.favorite} onChange={(e) => patch(c.id, { favorite: e.target.checked })} /> Favorite</label>
                    <label className="flex items-center gap-1.5"><input type="checkbox" checked={c.auto_process} onChange={(e) => patch(c.id, { auto_process: e.target.checked })} /> Auto-discover</label>
                    <button className="btn btn-danger" onClick={() => confirm(`Unfollow ${c.title}?`) && act.run(async () => { await api(`/creators/${c.id}`, { method: "DELETE" }); list.reload(); })}>Unfollow</button>
                  </div>
                </div>
                <label className="label mt-3" htmlFor={`t${c.id}`}>Topics of interest (comma separated)</label>
                <input id={`t${c.id}`} className="input" defaultValue={c.topics.join(", ")} placeholder="e.g. architecture, pricing"
                  onBlur={(e) => { const t = e.target.value.split(",").map((s) => s.trim()).filter(Boolean); if (t.join() !== c.topics.join()) patch(c.id, { topics: t }); }} />
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
