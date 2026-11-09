import { useEffect, useState } from "react";
import { api, getToken, setToken } from "./api";
import type { Me } from "./types";
import { ErrorBox, useAction } from "./ui";
import Home from "./pages/Home";
import Creators from "./pages/Creators";
import QuickAdd from "./pages/QuickAdd";
import VideoDetail from "./pages/VideoDetail";
import Library, { NoteView } from "./pages/Library";
import Topics from "./pages/Topics";
import CrossCheck from "./pages/CrossCheck";
import DigestPage from "./pages/Digest";
import Settings from "./pages/Settings";

const NAV = [
  ["#/", "Home Feed"], ["#/creators", "My Creators"], ["#/add", "Quick Add"], ["#/library", "Library"],
  ["#/topics", "Topics & Collections"], ["#/crosscheck", "Cross-Check"], ["#/digest", "Weekly Digest"], ["#/settings", "Settings"],
] as const;

function useHash() {
  const [h, setH] = useState(location.hash || "#/");
  useEffect(() => { const f = () => setH(location.hash || "#/"); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return h;
}

function Onboarding({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const { busy, error, run } = useAction();
  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-semibold">Creator Knowledge Hub</h1>
      <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">Follow creators you choose, keep your own notes, and search what you learned. Your library is private by default.</p>
      <form className="card mt-6 space-y-3" onSubmit={(e) => { e.preventDefault(); run(async () => { const r = await api("/users", { body: { name } }); setToken(r.token); onDone(); }); }}>
        <label className="label" htmlFor="nm">Your name</label>
        <input id="nm" className="input" value={name} onChange={(e) => setName(e.target.value)} required maxLength={80} autoFocus />
        <button className="btn btn-primary w-full" disabled={busy || !name.trim()}>Create local profile</button>
        {error != null && <ErrorBox error={error} />}
        <p className="text-xs text-slate-500">A random access token is stored in this browser. No password, no tracking. Nothing is sent to an AI provider unless you opt in under Settings.</p>
      </form>
    </main>
  );
}

export default function App() {
  const hash = useHash();
  const [me, setMe] = useState<Me | null>(null);
  const [authed, setAuthed] = useState(!!getToken());
  const [dark, setDark] = useState(document.documentElement.classList.contains("dark"));
  const [menu, setMenu] = useState(false);

  const loadMe = () => api<Me>("/me").then(setMe).catch(() => { setToken(""); setAuthed(false); });
  useEffect(() => { if (authed) loadMe(); }, [authed]);
  useEffect(() => { document.documentElement.classList.toggle("dark", dark); try { localStorage.setItem("ckh-theme", dark ? "dark" : "light"); } catch { /* ignore */ } }, [dark]);
  useEffect(() => { setMenu(false); window.scrollTo(0, 0); }, [hash]);

  if (!authed) return <Onboarding onDone={() => setAuthed(true)} />;

  const [, path = "", arg = ""] = hash.replace(/^#\//, "/").split("/");
  let page;
  switch (path) {
    case "": page = <Home />; break;
    case "creators": page = <Creators demo={me?.demo_mode} />; break;
    case "add": page = <QuickAdd />; break;
    case "video": page = <VideoDetail id={Number(arg)} me={me} />; break;
    case "library": page = <Library />; break;
    case "note": page = <NoteView id={Number(arg)} />; break;
    case "topics": page = <Topics />; break;
    case "crosscheck": page = <CrossCheck />; break;
    case "digest": page = <DigestPage />; break;
    case "settings": page = <Settings me={me} onChange={loadMe} />; break;
    default: page = <p>Page not found.</p>;
  }
  return (
    <div className="min-h-screen md:flex">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:p-2 dark:focus:bg-slate-900">Skip to content</a>
      <header className="flex items-center justify-between border-b border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 md:hidden">
        <strong>Creator Knowledge Hub</strong>
        <button className="btn" aria-expanded={menu} aria-controls="nav" onClick={() => setMenu(!menu)}>Menu</button>
      </header>
      <nav id="nav" aria-label="Main" className={`${menu ? "block" : "hidden"} w-full shrink-0 border-r border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 md:sticky md:top-0 md:block md:h-screen md:w-56`}>
        <p className="mb-3 hidden px-2 text-sm font-semibold md:block">Creator Knowledge Hub</p>
        <ul className="space-y-0.5">
          {NAV.map(([href, label]) => {
            const active = href === "#/" ? hash === "#/" || hash === "#" : hash.startsWith(href);
            return <li key={href}><a href={href} aria-current={active ? "page" : undefined} className={`block rounded-md px-2 py-1.5 text-sm ${active ? "bg-indigo-50 font-medium text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200" : "text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"}`}>{label}</a></li>;
          })}
        </ul>
        <div className="mt-4 border-t border-slate-200 pt-3 text-xs text-slate-500 dark:border-slate-800">
          {me?.demo_mode && <p className="mb-2 rounded bg-amber-50 p-2 text-amber-900 dark:bg-amber-950 dark:text-amber-200">Demo mode: synthetic YouTube data (no API key set).</p>}
          <p>Signed in as {me?.name}</p>
          <button className="btn mt-2 w-full" onClick={() => setDark(!dark)} aria-pressed={dark}>{dark ? "Light mode" : "Dark mode"}</button>
        </div>
      </nav>
      <main id="main" className="min-w-0 flex-1 p-4 md:p-8"><div className="mx-auto max-w-4xl">{page}</div></main>
    </div>
  );
}
