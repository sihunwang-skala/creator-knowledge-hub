export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) { super(message); this.status = status; this.code = code; }
}

const KEY = "ckh-token";
export const getToken = () => { try { return localStorage.getItem(KEY) ?? ""; } catch { return ""; } };
export const setToken = (t: string) => { try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ } };

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; form?: FormData; text?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }
  const res = await fetch(`/api${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  if (!res.ok) {
    let msg = res.statusText, code: string | undefined;
    try {
      const j = await res.json();
      const d = j.detail;
      if (typeof d === "string") msg = d;
      else if (d && typeof d === "object" && !Array.isArray(d)) { msg = d.message ?? msg; code = d.code; }
      else if (Array.isArray(d)) msg = d.map((x: any) => x.msg).join("; ");
    } catch { /* non-JSON error */ }
    throw new ApiError(res.status, msg, code);
  }
  return (opts.text ? await res.text() : await res.json()) as T;
}

export function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
