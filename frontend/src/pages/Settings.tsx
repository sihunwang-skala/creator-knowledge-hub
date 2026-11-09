import { useEffect, useState } from "react";
import { api, setToken } from "../api";
import type { Me } from "../types";
import { Badge, ErrorBox, PageHeader, useAction, useLoad } from "../ui";

export default function Settings({ me, onChange }: { me: Me | null; onChange: () => void }) {
  const policy = useLoad(() => api<any>("/policy"));
  const quota = useLoad(() => api<any>("/quota"));
  const [role, setRole] = useState("");
  const [interests, setInterests] = useState("");
  const [saved, setSaved] = useState(false);
  const [opt, setOpt] = useState({ youtube_channel_id: "", contact: "", allow_transcripts: false, allow_commercial: false, transcript_license: "" });
  const [optMsg, setOptMsg] = useState("");
  const act = useAction();
  useEffect(() => { if (me) { setRole(me.role_profile); setInterests(me.interests.join(", ")); } }, [me]);
  if (!me) return null;
  const save = (body: object) => act.run(async () => { await api("/me", { method: "PATCH", body }); onChange(); setSaved(true); setTimeout(() => setSaved(false), 1500); });
  return (
    <>
      <PageHeader title="Settings & Source Permissions" />
      {act.error != null && <div className="mb-3"><ErrorBox error={act.error} /></div>}
      <section className="card mb-5" aria-labelledby="pf"><h2 id="pf" className="mb-3 font-semibold">Personalisation</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <div><label className="label" htmlFor="rl">Your role (shapes emphasis)</label><input id="rl" className="input" value={role} onChange={(e) => setRole(e.target.value)} placeholder="software engineer, founder, researcher…" /></div>
          <div><label className="label" htmlFor="in">Interests (comma separated)</label><input id="in" className="input" value={interests} onChange={(e) => setInterests(e.target.value)} /></div>
          <div><label className="label" htmlFor="ds">Default note style</label><select id="ds" className="input" value={me.default_style} onChange={(e) => save({ default_style: e.target.value })}>{Object.entries(me.styles).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <div><label className="label" htmlFor="df">Digest delivery</label><select id="df" className="input" value={me.digest_frequency} onChange={(e) => save({ digest_frequency: e.target.value })}><option value="off">Off</option><option value="daily">Daily</option><option value="weekly">Weekly</option></select></div>
        </div>
        <button className="btn btn-primary mt-3" onClick={() => save({ role_profile: role, interests: interests.split(",").map((s) => s.trim()).filter(Boolean) })}>Save</button> {saved && <span role="status" className="ml-2 text-sm text-emerald-700">Saved</span>}
      </section>
      <section className="card mb-5" aria-labelledby="ai"><h2 id="ai" className="mb-2 font-semibold">AI processing & privacy</h2>
        <p className="text-sm">Summariser: <Badge tone={me.llm_provider === "local" ? "green" : "amber"}>{me.llm_provider === "local" ? "Local extractive (no data leaves this server)" : `External: ${me.llm_provider}`}</Badge></p>
        <label className="mt-3 flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={me.llm_consent} onChange={(e) => save({ llm_consent: e.target.checked })} />
          <span>Allow sending transcript text I attach to the configured external LLM provider. <span className="text-slate-500">Only sources you have approved are sent, only when you press Analyze or Regenerate. Your library is private and never sold or shared for advertising.</span></span></label>
        {quota.data && <p className="mt-3 text-xs text-slate-500">Today: YouTube API units {quota.data.youtube.used}/{quota.data.youtube.limit} · LLM calls {quota.data.llm.calls}/{quota.data.llm.limit} · view/subscriber filters {quota.data.stat_filters_enabled ? "enabled" : "disabled (policy review)"}</p>}
      </section>
      <section className="card mb-5" aria-labelledby="sp"><h2 id="sp" className="mb-2 font-semibold">Source permission policy</h2>
        {policy.data && <div className="space-y-2 text-sm">
          <p><strong>Allowed:</strong> {policy.data.enabled_methods.map((m: string) => <Badge key={m} tone="green">{m}</Badge>)}</p>
          <p><strong>Prohibited (cannot be enabled):</strong> {policy.data.prohibited_methods.map((m: string) => <Badge key={m} tone="red">{m}</Badge>)}</p>
          <p><strong>Disabled connectors:</strong> {Object.entries(policy.data.disabled).map(([k, v]) => <span key={k} className="mr-2"><Badge>{k}</Badge> <span className="text-slate-500">{String(v)}</span></span>)}</p>
          <p className="text-slate-500">{policy.data.notice}</p></div>}
      </section>
      <section className="card mb-5" aria-labelledby="co"><h2 id="co" className="mb-2 font-semibold">Creator opt-in</h2>
        <p className="mb-2 text-sm text-slate-500">Creators can register to offer transcripts under a license. Ownership verification needs YouTube OAuth and is not implemented; opt-in never lifts YouTube API restrictions.</p>
        <form className="grid gap-2 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); act.run(async () => { const r = await api("/creator-optin", { body: opt }); setOptMsg(r.note); }); }}>
          <div><label className="label" htmlFor="oc">Channel ID</label><input id="oc" className="input" value={opt.youtube_channel_id} onChange={(e) => setOpt({ ...opt, youtube_channel_id: e.target.value })} required /></div>
          <div><label className="label" htmlFor="ot">Contact</label><input id="ot" className="input" value={opt.contact} onChange={(e) => setOpt({ ...opt, contact: e.target.value })} required /></div>
          <div><label className="label" htmlFor="ol">Transcript license</label><input id="ol" className="input" value={opt.transcript_license} onChange={(e) => setOpt({ ...opt, transcript_license: e.target.value })} /></div>
          <div className="flex items-end gap-4 text-sm"><label><input type="checkbox" checked={opt.allow_transcripts} onChange={(e) => setOpt({ ...opt, allow_transcripts: e.target.checked })} /> Allow transcripts</label><label><input type="checkbox" checked={opt.allow_commercial} onChange={(e) => setOpt({ ...opt, allow_commercial: e.target.checked })} /> Commercial use</label></div>
          <div><button className="btn">Register interest</button></div>
        </form>{optMsg && <p role="status" className="mt-2 text-sm text-slate-600">{optMsg}</p>}
      </section>
      <section className="card border-red-300 dark:border-red-900" aria-labelledby="dl"><h2 id="dl" className="mb-2 font-semibold">Delete my data</h2>
        <p className="mb-3 text-sm text-slate-500">Permanently deletes your account, notes, stored source text, claims and digests from this server. This cannot be undone.</p>
        <button className="btn btn-danger" onClick={() => confirm("Delete ALL your data permanently?") && act.run(async () => { await api("/me", { method: "DELETE" }); setToken(""); location.hash = "#/"; location.reload(); })}>Delete everything</button>
      </section>
    </>
  );
}
