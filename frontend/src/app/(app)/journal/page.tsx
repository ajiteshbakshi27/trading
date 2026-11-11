"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, post } from "@/lib/api";
import Autopsy from "@/components/parakh/Autopsy";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Stat, inr, signedPct } from "@/components/parakh/ui";

export default function JournalPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [autopsy, setAutopsy] = useState<{ key: string; a: any } | null>(null);
  const [aBusy, setABusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api("/api/parakh/journal").then(setData).catch((e) => setErr(e.message));
  }, []);
  useEffect(load, [load]);

  const upload = async (file: File) => {
    setBusy(true); setErr(""); setMsg("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      const r = await api<any>("/api/parakh/journal/import", { method: "POST", body: fd });
      setMsg(`Imported ${r.added} trades (${r.skipped_duplicates} duplicates skipped) · format: ${r.format.replace("_", " ")}`);
      load();
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  const connect = async () => {
    try { window.location.href = (await api<any>("/api/parakh/broker/zerodha/login-url")).url; }
    catch (e: any) { setErr(e.message); }
  };

  const runAutopsy = async (t: any) => {
    const key = t.symbol + t.exit_at;
    setABusy(key);
    try { setAutopsy({ key, a: await post("/api/parakh/journal/autopsy", t) }); }
    catch (e: any) { setErr(e.message); } finally { setABusy(""); }
  };

  const clear = async () => {
    if (!confirm("Delete all imported trades? This can't be undone.")) return;
    await api("/api/parakh/journal", { method: "DELETE" });
    setAutopsy(null); load();
  };

  const s = data?.stats || {};
  return (
    <div className="space-y-4">
      <PageHeader title="Journal" subtitle="Import your real trades. Parakh pairs buys and sells, finds your habits, and explains losing trades." />
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          <Button onClick={() => fileRef.current?.click()} busy={busy}>Upload tradebook CSV</Button>
          <Button tone="ghost" onClick={connect}>Connect Zerodha (daily sync)</Button>
          {data?.trades > 0 && <Button tone="ghost" onClick={clear}>Clear journal</Button>}
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          Zerodha: Console → Reports → Tradebook → choose segment &amp; dates → download CSV. Other brokers: any CSV with
          symbol, buy/sell, quantity, price and date columns works. Duplicates are skipped automatically.
        </p>
        {msg && <p className="mt-2 text-sm text-emerald-300">{msg}</p>}
      </Card>
      <ErrorBox message={err} />
      {!data ? <Loading /> : data.trades === 0 ? (
        <Empty>No trades yet. Upload a tradebook CSV to see your stats and autopsies.</Empty>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-6">
            <Stat label="Round trips" value={s.n} />
            <Stat label="Win rate" value={`${Math.round((s.win_rate || 0) * 100)}%`} />
            <Stat label="Net P&L" value={inr(s.net_pnl, 0)} tone={s.net_pnl >= 0 ? "good" : "bad"} hint="before charges" />
            <Stat label="Avg win / loss" value={`${inr(s.avg_win, 0)} / ${inr(s.avg_loss, 0)}`} />
            <Stat label="Profit factor" value={s.profit_factor ?? "—"} />
            <Stat label="Hold: winners / losers" value={`${s.avg_hold_winners_days}d / ${s.avg_hold_losers_days}d`} />
          </div>
          {s.insights?.length > 0 && (
            <Card title="What your trades say about you">
              <ul className="list-disc space-y-1.5 pl-4 text-sm text-slate-200">{s.insights.map((i: string) => <li key={i}>{i}</li>)}</ul>
            </Card>
          )}
          {autopsy && <Autopsy a={autopsy.a} />}
          <Card title={`Closed trades (${data.round_trips.length})`} className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
                <tr><th className="py-2">Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>Days</th><th className="text-right">P&L</th><th className="text-right">Return</th><th /></tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {data.round_trips.map((t: any, i: number) => (
                  <tr key={i}>
                    <td className="py-2 font-medium text-white">{t.symbol}</td>
                    <td className="text-xs">{t.direction === "LONG" ? "Long" : "Short"}</td>
                    <td className="tabular-nums">{t.qty}</td>
                    <td className="text-xs tabular-nums">{inr(t.entry_price)}<div className="text-slate-500">{t.entry_at.slice(0, 10)}</div></td>
                    <td className="text-xs tabular-nums">{inr(t.exit_price)}<div className="text-slate-500">{t.exit_at.slice(0, 10)}</div></td>
                    <td className="tabular-nums">{t.holding_days}</td>
                    <td className={`text-right tabular-nums ${t.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{inr(t.pnl, 0)}</td>
                    <td className={`text-right tabular-nums ${t.return_pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{signedPct(t.return_pct)}</td>
                    <td className="pl-3 text-right">
                      <button onClick={() => runAutopsy(t)} className="text-xs text-sky-300 underline underline-offset-2 disabled:opacity-50" disabled={!!aBusy}>
                        {aBusy === t.symbol + t.exit_at ? "…" : "Autopsy"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-[11px] text-slate-500">{s.note}</p>
          </Card>
          {data.open_positions?.length > 0 && (
            <Card title="Still open (from imported trades)">
              <div className="flex flex-wrap gap-2 text-sm">
                {data.open_positions.map((p: any) => (
                  <span key={p.symbol} className="rounded-lg bg-white/5 px-2.5 py-1">{p.symbol} · {p.qty} @ {inr(p.avg_price)}</span>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
