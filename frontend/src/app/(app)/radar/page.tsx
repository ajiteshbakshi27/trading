"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, post } from "@/lib/api";
import { Button, Card, DataModeTag, ErrorBox, Loading, PageHeader, inputCls, inr, signedPct } from "@/components/parakh/ui";

const SIGNAL: Record<string, string> = {
  EUPHORIA: "bg-amber-500/15 text-amber-300", PANIC: "bg-rose-500/15 text-rose-300",
  HYPE_NO_PRICE: "bg-fuchsia-500/15 text-fuchsia-300", QUIET_MOVE: "bg-sky-500/15 text-sky-300",
};

export default function RadarPage() {
  const [wl, setWl] = useState<string[]>([]);
  const [text, setText] = useState("");
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setData(null);
    api<any>("/api/parakh/hype").then(setData).catch((e) => setErr(e.message));
  }, []);
  useEffect(() => {
    api<any>("/api/parakh/watchlist").then((j) => { setWl(j.symbols); setText(j.symbols.join(", ")); }).catch(() => {});
    load();
  }, [load]);

  const save = async () => {
    setBusy(true); setErr("");
    try {
      const j = await post<any>("/api/parakh/watchlist", { symbols: text.split(/[\s,]+/).filter(Boolean) }, "PUT");
      setWl(j.symbols); setText(j.symbols.join(", ")); load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const rows = data?.results || [];
  return (
    <div className="space-y-4">
      <PageHeader title="Hype radar" subtitle="Reddit chatter on Indian trading subs vs what price is actually doing. Divergence is the signal worth a second look." />
      <Card title="Your watchlist" action={<Link href="/settings" className="text-xs text-slate-400 underline">Telegram alerts →</Link>}>
        <div className="flex flex-col gap-2 sm:flex-row">
          <input className={inputCls} value={text} onChange={(e) => setText(e.target.value.toUpperCase())} placeholder="RELIANCE, HDFCBANK, TCS, BANKNIFTY" />
          <Button onClick={save} busy={busy}>Save</Button>
        </div>
        {!wl.length && <p className="mt-2 text-xs text-slate-500">Showing a default list until you add symbols.</p>}
      </Card>
      <ErrorBox message={err} />
      {!data ? <Loading label="Scanning…" /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr><th className="py-2">Symbol</th><th>Price</th><th>1d / 5d</th><th>Mentions 24h</th><th>Mood</th><th>Signal</th><th>Data</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {rows.map((r: any) => (
                <tr key={r.symbol} className="align-top">
                  <td className="py-2 font-medium text-white">{r.symbol}<div className="text-xs font-normal text-slate-500">{r.name}</div></td>
                  <td className="tabular-nums">{inr(r.price)}</td>
                  <td className="text-xs tabular-nums"><span className={r.change_1d_pct >= 0 ? "text-emerald-300" : "text-rose-300"}>{signedPct(r.change_1d_pct)}</span> / <span className={r.change_5d_pct >= 0 ? "text-emerald-300" : "text-rose-300"}>{signedPct(r.change_5d_pct)}</span></td>
                  <td className="tabular-nums">{r.mentions_24h} <span className="text-xs text-slate-500">(normal {r.baseline_per_day})</span></td>
                  <td className={r.sentiment > 0.2 ? "text-emerald-300" : r.sentiment < -0.2 ? "text-rose-300" : "text-slate-400"}>{r.sentiment > 0.2 ? "Bullish" : r.sentiment < -0.2 ? "Bearish" : "Mixed"}</td>
                  <td className="max-w-xs">{r.signal ? (
                    <><span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${SIGNAL[r.signal]}`}>{r.signal.replace(/_/g, " ").toLowerCase()}</span>
                      <div className="mt-1 text-xs text-slate-400">{r.note}</div></>
                  ) : <span className="text-xs text-slate-500">nothing unusual</span>}</td>
                  <td className="space-y-1 text-[10px]"><div>social: <DataModeTag mode={r.social_mode} /></div><div>price: <DataModeTag mode={r.price_mode} /></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {data?.alerts?.length > 0 && (
        <Card title="Recent alerts">
          <ul className="space-y-2 text-xs text-slate-300">
            {data.alerts.map((a: any) => <li key={a.id} className="whitespace-pre-wrap rounded-lg bg-white/[0.03] p-2">{a.message}<div className="mt-1 text-slate-500">{new Date(a.created_at).toLocaleString("en-IN")} · {a.delivered ? "sent to Telegram" : "not delivered"}</div></li>)}
          </ul>
        </Card>
      )}
    </div>
  );
}
