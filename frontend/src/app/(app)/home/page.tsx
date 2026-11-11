"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import { Button, Card, DataModeTag, Empty, ErrorBox, Loading, OutcomePill, inr, signedPct } from "@/components/parakh/ui";

export default function HomePage() {
  const [b, setB] = useState<any>(null);
  const [err, setErr] = useState("");
  const { session } = useSession();
  useEffect(() => { api("/api/parakh/brief?narrate=true").then(setB).catch((e) => setErr(e.message)); }, []);
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">{greet}{session?.name ? `, ${session.name}` : ""}</h1>
          <p className="text-sm text-slate-400">Your 1-minute brief.</p>
        </div>
        <Link href="/check"><Button>Check a trade idea</Button></Link>
      </div>
      <ErrorBox message={err} />
      {!b ? <Loading /> : (
        <>
          {b.summary && <Card><p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-200">{b.summary}</p></Card>}
          <div className="grid gap-3 sm:grid-cols-2">
            {[b.market.nifty, b.market.banknifty].map((q: any) => (
              <Card key={q.symbol}>
                <div className="flex items-center justify-between"><span className="text-sm text-slate-400">{q.name}</span><DataModeTag mode={q.data_mode} /></div>
                <div className="mt-1 flex items-baseline gap-3">
                  <span className="text-2xl font-bold tabular-nums text-white">{inr(q.price)}</span>
                  <span className={q.change_pct >= 0 ? "text-emerald-300" : "text-rose-300"}>{signedPct(q.change_pct)}</span>
                </div>
                <div className="text-[11px] text-slate-500">as of {q.as_of}</div>
              </Card>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Open ideas" className="lg:col-span-2" action={<Link href="/ideas" className="text-xs text-slate-400 underline">All</Link>}>
              {b.open_ideas.length === 0 ? <Empty>No open ideas. <Link className="underline" href="/check">Check one</Link>.</Empty> : (
                <ul className="divide-y divide-slate-800/70">
                  {b.open_ideas.map((o: any) => (
                    <li key={o.id} className="flex items-center justify-between py-2 text-sm">
                      <Link href={`/ideas/${o.id}`} className="font-medium text-white hover:underline">{o.symbol} <span className="text-xs text-slate-500">{o.direction === "LONG" ? "rise" : "fall"}</span></Link>
                      <span className="text-xs text-slate-400">{inr(o.price)} · {o.to_target_pct.toFixed(1)}% to target · <span className={o.near_stop ? "font-semibold text-rose-300" : ""}>{o.to_stop_pct.toFixed(1)}% to stop</span></span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
            <Card title="Calibration" action={<Link href="/calibration" className="text-xs text-slate-400 underline">Details</Link>}>
              {b.calibration.status === "ok"
                ? <><div className="text-3xl font-bold text-white">{b.calibration.score}<span className="text-sm text-slate-500">/100</span></div><p className="mt-1 text-xs text-slate-400">{b.calibration.verdict}</p></>
                : <p className="text-sm text-slate-400">{b.calibration.message}</p>}
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Recently resolved">
              {b.recently_resolved.length === 0 ? <p className="text-sm text-slate-400">Nothing resolved yet.</p> : (
                <ul className="space-y-2 text-sm">{b.recently_resolved.map((r: any) => (
                  <li key={r.id} className="flex items-center justify-between"><Link href={`/ideas/${r.id}`} className="hover:underline">{r.symbol}</Link>
                    <span className="flex items-center gap-2"><OutcomePill status={r.status} /><span className="tabular-nums text-xs">{signedPct(r.return_pct)}</span></span></li>
                ))}</ul>
              )}
            </Card>
            <Card title="Hype radar" action={<Link href="/radar" className="text-xs text-slate-400 underline">Open</Link>}>
              {!b.watchlist.length ? <p className="text-sm text-slate-400">Add a watchlist in <Link className="underline" href="/radar">Hype radar</Link> to get alerts.</p>
                : b.hype_alerts.length === 0 ? <p className="text-sm text-slate-400">Nothing unusual on your watchlist.</p> : (
                <ul className="space-y-2 text-sm">{b.hype_alerts.map((h: any) => (
                  <li key={h.symbol}><span className="font-medium text-white">{h.symbol}</span> <span className="text-xs text-slate-400">· {h.signal.replace(/_/g, " ").toLowerCase()} — {h.note}</span></li>
                ))}</ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
