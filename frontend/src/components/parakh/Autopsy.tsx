"use client";
import { Card, inr, signedPct } from "./ui";

export default function Autopsy({ a }: { a: any }) {
  if (!a) return null;
  const win = a.outcome === "win";
  return (
    <Card title={<span>Autopsy · <span className={win ? "text-emerald-300" : "text-rose-300"}>{win ? "Win" : "Loss"} {signedPct(a.return_pct)}</span></span>}>
      <p className="text-xs text-slate-500">
        {a.entry_date} {inr(a.entry_price)} → {a.exit_date} {inr(a.exit_price)}
      </p>
      {a.narrative && <p className="mt-3 text-sm leading-relaxed text-slate-200">{a.narrative}</p>}
      {a.failure_modes?.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {a.failure_modes.map((m: any) => (
            <li key={m.mode} className="rounded-lg bg-white/[0.03] p-2.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-medium text-slate-200">{m.label}</span>
                <span className="text-[11px] text-slate-500">likelihood {Math.round(m.likelihood * 100)}%</span>
              </div>
              <div className="mt-0.5 text-xs text-slate-400">{m.evidence}</div>
            </li>
          ))}
        </ul>
      ) : null}
      <div className="mt-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-2.5 text-sm text-emerald-100">
        <span className="font-semibold">Lesson: </span>{a.top_lesson}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">{a.method}</p>
    </Card>
  );
}
