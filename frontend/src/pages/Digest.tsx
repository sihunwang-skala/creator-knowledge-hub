import { api, download } from "../api";
import { Empty, ErrorBox, Markdown, PageHeader, Spinner, useAction, useLoad } from "../ui";

export default function DigestPage() {
  const list = useLoad(() => api<{ id: number; frequency: string; markdown: string; created_at: string }[]>("/digests"));
  const act = useAction();
  const gen = (f: string) => act.run(async () => { await api(`/digests?frequency=${f}`, { method: "POST" }); list.reload(); });
  return (
    <>
      <PageHeader title="Weekly Digest" sub="What’s new, what repeated, and what changed. Choose automatic delivery in Settings.">
        <button className="btn" disabled={act.busy} onClick={() => gen("daily")}>Generate daily</button>
        <button className="btn btn-primary" disabled={act.busy} onClick={() => gen("weekly")}>Generate weekly</button>
      </PageHeader>
      {act.error != null && <ErrorBox error={act.error} />}
      {list.loading ? <Spinner /> : list.error ? <ErrorBox error={list.error} onRetry={list.reload} /> :
        list.data!.length === 0 ? <Empty title="No digests yet">Generate one to summarise recent activity.</Empty> :
          <div className="space-y-4">{list.data!.map((d, i) => (
            <details key={d.id} open={i === 0} className="card"><summary className="cursor-pointer font-medium capitalize">{d.frequency} digest — {d.created_at.slice(0, 10)}</summary>
              <div className="mt-3"><Markdown text={d.markdown} /><button className="btn mt-3" onClick={() => download(`digest-${d.id}.md`, d.markdown)}>Export Markdown</button></div></details>))}</div>}
    </>
  );
}
