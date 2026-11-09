import { useState } from "react";
import { api } from "../api";
import type { Creator, UserVideo } from "../types";
import { Badge, Empty, ErrorBox, PageHeader, Spinner, useAction, useLoad } from "../ui";
import { ANALYSIS_LABEL, formatDuration, timeAgo } from "../utils";

export default function Home() {
  const [creator, setCreator] = useState("");
  const creators = useLoad(() => api<Creator[]>("/creators"));
  const feed = useLoad(() => api<UserVideo[]>(`/feed${creator ? `?channel_id=${creator}` : ""}`), [creator]);
  const act = useAction();

  const refresh = () => act.run(async () => { const r = await api("/feed/refresh", { method: "POST" }); await feed.reload(); return r; });
  const hide = (id: number) => act.run(async () => { await api(`/videos/${id}/hide`, { method: "POST" }); feed.reload(); });
  const add = (u: UserVideo) => act.run(async () => { await api("/videos/quick-add", { body: { url: u.video.youtube_video_id } }); location.hash = `#/video/${u.id}`; });

  return (
    <>
      <PageHeader title="Home Feed" sub="New uploads from creators you chose.">
        {creators.data && creators.data.length > 0 && (
          <select aria-label="Filter by creator" className="input !w-auto" value={creator} onChange={(e) => setCreator(e.target.value)}>
            <option value="">All creators</option>
            {creators.data.map((c) => <option key={c.id} value={c.channel_id}>{c.title}</option>)}
          </select>
        )}
        <button className="btn btn-primary" onClick={refresh} disabled={act.busy}>{act.busy ? "Checking…" : "Check for new videos"}</button>
      </PageHeader>
      {act.error != null && <div className="mb-3"><ErrorBox error={act.error} /></div>}
      {feed.loading ? <Spinner /> : feed.error ? <ErrorBox error={feed.error} onRetry={feed.reload} /> :
        feed.data!.length === 0 ? (
          <Empty title="Your feed is empty">
            {creators.data?.length ? "No new videos yet. Use “Check for new videos”." : <>Start by <a className="underline" href="#/creators">adding creators</a> you want to follow.</>}
          </Empty>
        ) : (
          <ul className="space-y-3">
            {feed.data!.map((u) => {
              const st = ANALYSIS_LABEL[u.analysis_status] ?? ANALYSIS_LABEL.not_started;
              return (
                <li key={u.id} className="card">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <a href={`#/video/${u.id}`} className="font-medium hover:underline">{u.video.title}</a>
                      <p className="mt-0.5 text-sm text-slate-600 dark:text-slate-400">{u.video.channel} · {timeAgo(u.video.published_at)} · {formatDuration(u.video.duration_sec)}</p>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <Badge tone={st.tone}>{st.text}</Badge>
                        {u.video.is_demo && <Badge tone="amber">Demo data</Badge>}
                        {u.video.has_caption_flag && <Badge>Has captions on YouTube</Badge>}
                        {!u.topic_match && <Badge>Outside your topics</Badge>}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button className="btn btn-primary" onClick={() => add(u)} disabled={act.busy}>Add to library</button>
                      <button className="btn" onClick={() => hide(u.id)} disabled={act.busy} aria-label={`Hide ${u.video.title}`}>Hide</button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
    </>
  );
}
