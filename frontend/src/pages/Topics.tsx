import { useState } from "react";
import { api, download } from "../api";
import type { Note } from "../types";
import { Empty, ErrorBox, Markdown, PageHeader, Spinner, useAction, useLoad } from "../ui";

export default function Topics() {
  const topics = useLoad(() => api<{ tag: string; count: number }[]>("/topics"));
  const cols = useLoad(() => api<{ id: number; name: string }[]>("/collections"));
  const notes = useLoad(() => api<Note[]>("/notes"));
  const syn = useLoad(() => api<{ id: number; topic: string; markdown: string; stats: any }[]>("/synthesis"));
  const [name, setName] = useState("");
  const [topic, setTopic] = useState("");
  const [sel, setSel] = useState<number[]>([]);
  const act = useAction();
  const toggle = (id: number) => setSel(sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id]);
  return (
    <>
      <PageHeader title="Topics & Collections" sub="Organise notes and merge what several videos say about one topic." />
      <section className="card mb-5" aria-labelledby="tp"><h2 id="tp" className="mb-2 font-semibold">Topics</h2>
        {topics.loading ? <Spinner /> : topics.data!.length === 0 ? <p className="text-sm text-slate-500">Tags appear here once you have notes.</p> :
          <div className="flex flex-wrap gap-2">{topics.data!.map((t) => <a key={t.tag} className="btn" href={`#/library?tag=${encodeURIComponent(t.tag)}`}>{t.tag} <span className="text-slate-500">{t.count}</span></a>)}</div>}
      </section>
      <section className="card mb-5" aria-labelledby="co"><h2 id="co" className="mb-2 font-semibold">Collections</h2>
        <form className="mb-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api("/collections", { body: { name } }); setName(""); cols.reload(); }); }}>
          <input aria-label="New collection name" className="input" placeholder="New collection" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} />
          <button className="btn" disabled={!name.trim() || act.busy}>Create</button>
        </form>
        <ul className="space-y-1 text-sm">{cols.data?.map((c) => <li key={c.id} className="flex items-center justify-between"><span>{c.name} <span className="text-slate-500">({notes.data?.filter((n) => n.collection_id === c.id).length ?? 0})</span></span><button className="btn btn-danger" onClick={() => act.run(async () => { await api(`/collections/${c.id}`, { method: "DELETE" }); cols.reload(); })}>Delete</button></li>)}</ul>
        {notes.data && notes.data.length > 0 && cols.data && cols.data.length > 0 && (
          <div className="mt-3"><label className="label" htmlFor="mv">Move a note into a collection</label>
            <div className="flex flex-wrap gap-2"><select id="mv" className="input !w-auto" defaultValue="" onChange={(e) => { const [nid, cid] = e.target.value.split(":"); if (nid) act.run(async () => { await api(`/notes/${nid}`, { method: "PATCH", body: { collection_id: Number(cid) } }); notes.reload(); }); }}>
              <option value="">Select…</option>{notes.data.flatMap((n) => cols.data!.map((c) => <option key={`${n.id}:${c.id}`} value={`${n.id}:${c.id}`}>{n.title.slice(0, 40)} → {c.name}</option>))}</select></div></div>)}
      </section>
      <section className="card" aria-labelledby="sy"><h2 id="sy" className="mb-2 font-semibold">Knowledge synthesis</h2>
        {notes.data?.length === 0 ? <Empty title="No notes to combine yet" /> : (
          <form onSubmit={(e) => { e.preventDefault(); act.run(async () => { await api("/synthesis", { body: { topic, note_ids: sel } }); setSel([]); syn.reload(); }); }}>
            <label className="label" htmlFor="tpc">Topic title</label><input id="tpc" className="input mb-2" value={topic} onChange={(e) => setTopic(e.target.value)} />
            <fieldset><legend className="label">Choose notes to merge</legend>
              <ul className="mb-2 max-h-48 space-y-1 overflow-auto text-sm">{notes.data?.map((n) => <li key={n.id}><label className="flex gap-2"><input type="checkbox" checked={sel.includes(n.id)} onChange={() => toggle(n.id)} />{n.title} <span className="text-slate-500">— {n.video.channel}</span></label></li>)}</ul></fieldset>
            <button className="btn btn-primary" disabled={!topic.trim() || sel.length === 0 || act.busy}>Create synthesis ({sel.length})</button>
          </form>)}
        {act.error != null && <div className="mt-3"><ErrorBox error={act.error} /></div>}
        {syn.data?.map((s) => <details key={s.id} className="mt-4 rounded-md border border-slate-200 p-3 dark:border-slate-800"><summary className="cursor-pointer font-medium">{s.topic} <span className="text-xs text-slate-500">({s.stats.notes} notes, {s.stats.deduped} duplicates merged)</span></summary>
          <div className="mt-3"><Markdown text={s.markdown} /><button className="btn mt-3" onClick={() => download(`synthesis-${s.id}.md`, s.markdown)}>Download Markdown</button></div></details>)}
      </section>
    </>
  );
}
