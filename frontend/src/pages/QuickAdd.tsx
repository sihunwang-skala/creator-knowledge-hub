import { useState } from "react";
import { api } from "../api";
import { ErrorBox, PageHeader, useAction } from "../ui";
import { parseVideoRef } from "../utils";

export default function QuickAdd() {
  const [url, setUrl] = useState("");
  const act = useAction();
  const valid = parseVideoRef(url) !== null;
  return (
    <>
      <PageHeader title="Quick Add" sub="Paste a YouTube video link to add it to your library." />
      <form className="card space-y-3" onSubmit={(e) => { e.preventDefault(); act.run(async () => { const u = await api("/videos/quick-add", { body: { url } }); location.hash = `#/video/${u.id}`; }); }}>
        <label className="label" htmlFor="u">Video URL</label>
        <input id="u" className="input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" aria-invalid={!!url && !valid} aria-describedby="uh" />
        <p id="uh" className={`text-xs ${url && !valid ? "text-red-600" : "text-slate-500"}`}>{url && !valid ? "That does not look like a YouTube video link." : "Metadata and a bookmark are saved immediately. AI analysis only starts once you attach a source you have permission to use."}</p>
        {act.error != null && <ErrorBox error={act.error} />}
        <button className="btn btn-primary" disabled={!valid || act.busy}>{act.busy ? "Adding…" : "Add video"}</button>
      </form>
    </>
  );
}
