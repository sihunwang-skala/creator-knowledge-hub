import { useState } from "react";
import { api } from "../api";
import type { Claim } from "../types";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, useAction, useLoad } from "../ui";
import { VERDICT_LABEL } from "../utils";

export default function CrossCheck() {
  const [verdict, setVerdict] = useState("");
  const claims = useLoad(() => api<Claim[]>(`/claims${verdict ? `?verdict=${verdict}` : ""}`), [verdict]);
  const act = useAction();
  return (
    <>
      <PageHeader title="Cross-Check Results" sub="Factual claims from your videos, compared with independent sources.">
        <select aria-label="Filter by verdict" className="input !w-auto" value={verdict} onChange={(e) => setVerdict(e.target.value)}>
          <option value="">All</option>{Object.entries(VERDICT_LABEL).map(([k, v]) => <option key={k} value={k}>{v.text}</option>)}
        </select>
      </PageHeader>
      <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">Copies of the same original count as one source. If nothing is found, a claim stays “Insufficient evidence” — never assumed true.</p>
      {act.error != null && <ErrorBox error={act.error} />}
      {claims.loading ? <Spinner /> : claims.error ? <ErrorBox error={claims.error} onRetry={claims.reload} /> :
        claims.data!.length === 0 ? <Empty title="No claims here">Claims are extracted when a note is created. <a className="underline" href="#/library">Open the library</a></Empty> : (
          <ul className="space-y-3">{claims.data!.map((c) => { const v = VERDICT_LABEL[c.verdict] ?? VERDICT_LABEL.unchecked; return (
            <li key={c.id} className="card text-sm">
              <div className="flex flex-wrap items-center gap-2"><Badge tone={v.tone}>{v.text}</Badge><Badge>{c.kind}</Badge><a className="text-xs underline" href={`#/note/${c.note_id}`}>open note</a></div>
              <p className="mt-2">{c.text}</p>{c.rationale && <p className="mt-1 text-slate-500">{c.rationale}</p>}
              <ul className="mt-2 space-y-1">{c.evidence.map((e, i) => <li key={i}><Badge tone={e.stance === "supports" ? "green" : e.stance === "contradicts" ? "red" : "gray"}>{e.stance}</Badge> <a className="underline" href={e.url} target="_blank" rel="noopener noreferrer">{e.title || e.url}</a> <span className="text-xs text-slate-500">origin {e.origin} · {e.retrieved_at.slice(0, 10)}</span></li>)}</ul>
              <button className="btn mt-2" disabled={act.busy} onClick={() => act.run(async () => { await api(`/claims/${c.id}/check`, { method: "POST" }); claims.reload(); })}>{c.verdict === "unchecked" ? "Cross-check" : "Re-check"}</button>
            </li>); })}</ul>
        )}
    </>
  );
}
