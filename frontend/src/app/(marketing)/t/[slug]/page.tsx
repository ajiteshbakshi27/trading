"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { API } from "@/lib/api";

const STATUS: Record<string, string> = { open: "Open — still being tracked", hit: "Target hit", miss: "Stopped out", expired: "Timed out" };

async function sha256(text: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
function canonical(o: Record<string, any>) {
  // Python json.dumps(sort_keys=True, separators=(",", ":")) with ASCII escaping
  const keys = Object.keys(o).sort();
  const esc = (s: string) => JSON.stringify(s).replace(/[\u0080-\uffff]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0"));
  const val = (v: any) => (typeof v === "string" ? esc(v) : String(v));
  return "{" + keys.map((k) => `${esc(k)}:${val(o[k])}`).join(",") + "}";
}

export default function PublicThesis() {
  const { slug } = useParams<{ slug: string }>();
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [verified, setVerified] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${API}/api/parakh/public/thesis/${slug}`).then(async (r) => {
      if (!r.ok) throw new Error("This idea doesn't exist or isn't public.");
      const j = await r.json();
      setD(j);
      setVerified((await sha256(canonical(j.terms))) === j.seal);
    }).catch((e) => setErr(e.message));
  }, [slug]);

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <Link href="/" className="text-sm text-slate-400">← Parakh</Link>
      {err && <p className="mt-6 text-rose-300">{err}</p>}
      {d && (
        <div className="mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
          <p className="text-xs uppercase tracking-wide text-slate-500">Shared by @{d.author}</p>
          <h1 className="mt-1 text-2xl font-bold text-white">{d.name || d.terms.symbol}: expects {d.terms.direction === "LONG" ? "a rise" : "a fall"}</h1>
          <p className="mt-2 text-slate-300">&ldquo;{d.terms.idea_text}&rdquo;</p>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-slate-500">Entry</dt><dd className="text-white">₹{d.terms.entry_price}</dd></div>
            <div><dt className="text-slate-500">Target / stop</dt><dd className="text-white">₹{d.terms.target_price} / ₹{d.terms.stop_price}</dd></div>
            <div><dt className="text-slate-500">Within</dt><dd className="text-white">{d.terms.horizon_days} trading days</dd></div>
            <div><dt className="text-slate-500">Stated confidence</dt><dd className="text-white">{Math.round(Number(d.terms.user_confidence) * 100)}%</dd></div>
            <div><dt className="text-slate-500">Status</dt><dd className="text-white">{STATUS[d.status] || d.status}{d.outcome_return_pct != null && ` (${d.outcome_return_pct > 0 ? "+" : ""}${d.outcome_return_pct}%)`}</dd></div>
            <div><dt className="text-slate-500">Recorded</dt><dd className="text-white">{d.terms.created_at} UTC</dd></div>
          </dl>
          <div className={`mt-5 rounded-lg p-3 text-xs ${verified ? "bg-emerald-500/10 text-emerald-300" : verified === false ? "bg-amber-500/10 text-amber-300" : "bg-white/5 text-slate-400"}`}>
            {verified ? "✓ Seal verified in your browser — these terms haven't changed since they were recorded."
              : verified === false ? "Couldn't verify the seal in this browser; the server reports: " + (d.seal_valid ? "valid" : "INVALID") : "Verifying seal…"}
            <div className="mt-1 break-all text-slate-500">SHA-256: {d.seal}</div>
          </div>
          {d.data_mode !== "live" && <p className="mt-3 text-xs text-amber-300">Tracked on simulated price data (live data was unavailable).</p>}
          <p className="mt-4 text-[11px] text-slate-500">Parakh records ideas; it does not give investment advice.</p>
        </div>
      )}
    </main>
  );
}
