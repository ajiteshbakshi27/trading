"use client";
import { Card, DataModeTag, StatusPill, Stat, inr, pct } from "./ui";

export type Report = any;

function OddsBar({ label, value, tone }: { label: string; value: number | null | undefined; tone: string }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{label}</span><span className="tabular-nums text-slate-200">{value == null ? "n/a" : pct(value)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-white/5">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${Math.max(0, Math.min(1, value ?? 0)) * 100}%` }} />
      </div>
    </div>
  );
}

export default function ThesisReport({ r }: { r: Report }) {
  const score = r.checklist_score ?? 0;
  const scoreTone = score >= 70 ? "text-emerald-300" : score >= 45 ? "text-amber-300" : "text-rose-300";
  const analog = r.analogues || {};
  const stress = r.stress || {};
  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className={`rounded-md px-2 py-0.5 text-xs font-bold ${r.direction === "LONG" ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                {r.direction === "LONG" ? "EXPECTS RISE" : "EXPECTS FALL"}
              </span>
              <DataModeTag mode={r.data_mode} />
              {r.parse_mode === "claude" && <span className="text-[10px] text-slate-500">parsed by Claude</span>}
            </div>
            <h2 className="mt-2 text-xl font-bold text-white">{r.name} <span className="text-sm font-normal text-slate-400">({r.symbol})</span></h2>
            <p className="text-xs text-slate-500">Priced on {r.as_of} · {r.horizon_days} trading days{r.catalyst ? ` · catalyst: ${r.catalyst}` : ""}</p>
          </div>
          <div className="text-right">
            <div className={`text-4xl font-bold tabular-nums ${scoreTone}`}>{score}<span className="text-base text-slate-500">/100</span></div>
            <div className="text-[11px] text-slate-500">checklist score (not a prediction)</div>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Entry (last close)" value={inr(r.entry_price)} />
          <Stat label="Target" value={inr(r.target_price)} tone="good" />
          <Stat label="Stop" value={inr(r.stop_price)} tone="bad" />
          <Stat label="Reward : risk" value={`${r.reward_risk} : 1`} hint={`ATR ${inr(r.atr)}`} />
        </div>
        {r.fixes?.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-amber-300">{r.fixes.map((f: string) => <li key={f}>⚠ {f}</li>)}</ul>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="The checklist" className="lg:col-span-3">
          <ul className="divide-y divide-slate-800/70">
            {r.checks.map((c: any) => (
              <li key={c.id} className="flex items-start gap-3 py-2.5">
                <div className="w-20 shrink-0 pt-0.5"><StatusPill status={c.status} /></div>
                <div>
                  <div className="text-sm font-medium text-slate-200">{c.title}</div>
                  <div className="text-xs leading-relaxed text-slate-400">{c.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-4 lg:col-span-2">
          <Card title="Your confidence vs the odds">
            <div className="space-y-3">
              <OddsBar label="You said" value={r.user_confidence} tone="bg-sky-400" />
              <OddsBar label={`Similar past setups (n=${analog.n ?? 0})`} value={analog.hit_rate} tone="bg-emerald-400" />
              <OddsBar label="Pure chance (random walk)" value={r.chance_odds?.p_target} tone="bg-slate-400" />
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
              {analog.hit_rate == null ? analog.note + " " : ""}Probability the target is reached before the stop within {r.horizon_days} days.
              Pure chance uses this stock&apos;s own volatility with zero drift (2,000 simulations).
            </p>
          </Card>

          <Card title="What would prove you wrong">
            <ul className="list-disc space-y-1.5 pl-4 text-sm text-slate-300">
              {r.what_proves_you_wrong.map((w: string) => <li key={w}>{w}</li>)}
            </ul>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Stress test">
          {stress.error ? <p className="text-sm text-slate-400">{stress.error}</p> : (
            <>
              <p className="text-sm text-slate-300">
                Price-based model leans <b>{stress.model_direction}</b>
                {stress.model_agrees === true && " — agrees with you"}
                {stress.model_agrees === false && " — disagrees with you"}
                {stress.label && <> · <span className="text-slate-400">{stress.label}</span></>}
              </p>
              <ul className="mt-2 space-y-1 text-xs">
                {(stress.scenarios || []).map((s: any) => (
                  <li key={s.scenario} className="flex justify-between">
                    <span className="text-slate-400">{s.scenario}</span>
                    <span className={s.survives ? "text-emerald-300" : "text-rose-300"}>{s.survives ? "holds" : s.flipped ? "flips" : "fails"}</span>
                  </li>
                ))}
              </ul>
              {stress.not_applicable?.length > 0 && (
                <p className="mt-2 text-[11px] text-slate-500">Not applicable (no data for that layer): {stress.not_applicable.join(", ")}.</p>
              )}
            </>
          )}
        </Card>
        <Card title="Events that can move it">
          {r.related_events?.length ? (
            <ul className="space-y-2 text-sm">
              {r.related_events.map((e: any) => (
                <li key={e.event}><span className="font-medium text-slate-200">{e.name}</span>
                  <span className="block text-xs text-slate-400">{e.sensitivity}</span></li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-400">No mapped events for this symbol.</p>}
        </Card>
      </div>
      <p className="text-[11px] text-slate-500">{r.disclaimer}</p>
    </div>
  );
}
