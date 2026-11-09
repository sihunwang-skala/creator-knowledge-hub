import { ReactNode, useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";

const TONES = {
  gray: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  amber: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-300",
  red: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  blue: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
};
export function Badge({ tone = "gray", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>;
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return <p role="status" className="py-8 text-center text-sm text-slate-500">{label}</p>;
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-slate-600 dark:text-slate-400">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as ApiError;
  const perm = e?.status === 403 || e?.status === 409 || e?.status === 412;
  return (
    <div role="alert" className={`rounded-md border p-3 text-sm ${perm ? "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200" : "border-red-300 bg-red-50 text-red-900 dark:border-red-900 dark:bg-red-950 dark:text-red-200"}`}>
      <strong>{perm ? "Permission required: " : "Error: "}</strong>{e?.message ?? "Something went wrong"}
      {onRetry && <button className="btn ml-3" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fn().then(setData).catch(setError).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(reload, [reload]);
  return { data, error, loading, reload, setData };
}

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError(null);
    try { return await fn(); } catch (e) { setError(e); } finally { setBusy(false); }
  };
  return { busy, error, run, clear: () => setError(null) };
}

export function PageHeader({ title, children, sub }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div><h1 className="text-xl font-semibold">{title}</h1>{sub && <p className="text-sm text-slate-600 dark:text-slate-400">{sub}</p>}</div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

/** Minimal, safe markdown renderer (headings, bullets, bold, links). No raw HTML is ever injected. */
export function Markdown({ text }: { text: string }) {
  const inline = (s: string, k: string) => {
    const parts: ReactNode[] = [];
    const re = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)|\*\*([^*]+)\*\*|_\(([^)]+)\)_/g;
    let last = 0, m: RegExpExecArray | null, i = 0;
    while ((m = re.exec(s))) {
      if (m.index > last) parts.push(s.slice(last, m.index));
      if (m[1]) parts.push(<a key={`${k}${i++}`} href={m[2]} target="_blank" rel="noopener noreferrer" className="text-indigo-700 underline dark:text-indigo-300">{m[1]}</a>);
      else if (m[3]) parts.push(<strong key={`${k}${i++}`}>{m[3]}</strong>);
      else parts.push(<em key={`${k}${i++}`} className="text-slate-500">({m[4]})</em>);
      last = m.index + m[0].length;
    }
    parts.push(s.slice(last));
    return parts;
  };
  return (
    <div className="space-y-1 text-sm leading-relaxed">
      {text.split("\n").map((line, i) => {
        if (/^#{1,3} /.test(line)) {
          const lvl = line.match(/^#+/)![0].length;
          const cls = lvl === 1 ? "mt-2 text-lg font-semibold" : lvl === 2 ? "mt-4 text-base font-semibold" : "mt-3 font-semibold";
          return <p key={i} className={cls}>{inline(line.replace(/^#+ /, ""), `h${i}`)}</p>;
        }
        if (/^\s*- /.test(line)) return <p key={i} className={`flex gap-2 ${/^\s{2,}/.test(line) ? "ml-5" : ""}`}><span aria-hidden>•</span><span>{inline(line.replace(/^\s*- (\[ \] )?/, ""), `l${i}`)}</span></p>;
        if (line.startsWith("> ")) return <p key={i} className="border-l-2 border-slate-300 pl-3 text-slate-600 dark:border-slate-700 dark:text-slate-400">{inline(line.slice(2), `q${i}`)}</p>;
        return line.trim() ? <p key={i}>{inline(line, `p${i}`)}</p> : <div key={i} className="h-1" />;
      })}
    </div>
  );
}
