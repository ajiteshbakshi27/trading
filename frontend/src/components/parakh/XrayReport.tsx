"use client";
import { Card, Empty, Stat, inr } from "./ui";

const TAG: Record<string, { label: string; cls: string }> = {
  leak: { label: "Losing habit", cls: "bg-rose-500/15 text-rose-300" },
  loss_shape: { label: "Shape of your losses", cls: "bg-amber-500/15 text-amber-300" },
  no_leak: { label: "Not a problem", cls: "bg-emerald-500/15 text-emerald-300" },
  insufficient_data: { label: "Too few trades to say", cls: "bg-slate-500/20 text-slate-300" },
  needs_times: { label: "Needs trade times", cls: "bg-slate-500/20 text-slate-300" },
  not_seen: { label: "Not seen", cls: "bg-slate-500/20 text-slate-300" },
};

function Pattern({ p, floor }: { p: any; floor: number }) {
  const tag = TAG[p.status] || TAG.not_seen;
  const measured = ["leak", "loss_shape", "no_leak"].includes(p.status);
  return (
    <div className="rounded-xl border border-slate-800/80 bg-white/[0.02] p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-white">{p.title}</h3>
          <p className="mt-0.5 text-xs text-slate-400">{p.what}</p>
        </div>
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${tag.cls}`}>{tag.label}</span>
      </div>
      {measured ? (
        <>
          <div className={`mt-3 text-2xl font-bold tabular-nums ${p.net_pnl < 0 ? "text-rose-300" : "text-emerald-300"}`}>
            {inr(p.net_pnl, 0)}
            <span className="ml-2 text-sm font-normal text-slate-400">across {p.n} trades</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-400">
            {p.kind === "habit" && <span>Win rate {Math.round((p.win_rate || 0) * 100)}%</span>}
            <span>Average {inr(p.avg_pnl, 0)} per trade</span>
            {p.kind === "habit" && p.avg_pnl_other_trades != null && <span>Your other trades: {inr(p.avg_pnl_other_trades, 0)} per trade</span>}
            {p.share_of_all_losses != null && <span>{Math.round(p.share_of_all_losses * 100)}% of all the money you lost</span>}
          </div>
          {p.note && <p className="mt-2 text-[11px] text-slate-500">{p.note}</p>}
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-400">
          {p.status === "needs_times" ? "Your file has dates but no trade times, so this can't be measured."
            : p.status === "insufficient_data" ? `Only ${p.n} such trades. Parakh needs at least ${floor} before calling it a habit.`
            : "No trades like this in your tradebook."}
        </p>
      )}
    </div>
  );
}

export default function XrayReport({ data }: { data: any }) {
  const x = data?.xray;
  const s = data?.stats || {};
  if (!x) return null;
  if (x.status !== "ok") return <Empty>{x.headline}</Empty>;
  return (
    <div className="space-y-4">
      {data.sample && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
          {data.sample_label}
        </div>
      )}
      <Card>
        <div className="text-[11px] uppercase tracking-wide text-slate-500">Biggest finding · {x.period.from} to {x.period.to}</div>
        <p className="mt-1 text-xl font-semibold leading-snug text-white sm:text-2xl">{x.headline}</p>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="Closed trades" value={x.n_trips} />
          <Stat label="Net P&L" value={inr(x.net_pnl, 0)} tone={x.net_pnl >= 0 ? "good" : "bad"} hint="before charges" />
          <Stat label="Win rate" value={`${Math.round((s.win_rate || 0) * 100)}%`} />
          <Stat label="Avg win / loss" value={`${inr(s.avg_win, 0)} / ${inr(s.avg_loss, 0)}`} />
        </div>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {x.patterns.map((p: any) => <Pattern key={p.id} p={p} floor={x.pattern_floor} />)}
      </div>
      <p className="text-[11px] leading-relaxed text-slate-500">
        {x.caveat} {x.overlap_note} {x.charges_note} This is a description of past trades, not advice.
      </p>
    </div>
  );
}
