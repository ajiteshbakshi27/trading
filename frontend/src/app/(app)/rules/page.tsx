"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, post } from "@/lib/api";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Stat, inputCls, inr } from "@/components/parakh/ui";

type RuleDef = { id: string; label: string; hint: string; kind: "number" | "toggle"; min?: number; max?: number; step?: number; example?: number };

const IDEA_RULES: RuleDef[] = [
  { id: "min_reward_risk", label: "Reward must be at least this many times the risk", hint: "Checked on every idea you check.", kind: "number", min: 0.5, max: 10, step: 0.5, example: 2 },
  { id: "with_trend_only", label: "No trades against the trend", hint: "Flags an idea that fights both the 50-day and 200-day averages.", kind: "toggle" },
  { id: "min_checklist_score", label: "Checklist score must be at least", hint: "Out of 100.", kind: "number", min: 1, max: 100, step: 5, example: 60 },
];
const DAY_RULES: RuleDef[] = [
  { id: "max_trades_per_day", label: "At most this many trades a day", hint: "Counted from your journal.", kind: "number", min: 1, max: 50, step: 1, example: 3 },
  { id: "stop_after_losses", label: "Stop for the day after this many losing trades", hint: "Needs trade times in your journal.", kind: "number", min: 1, max: 20, step: 1, example: 2 },
  { id: "cool_off_minutes", label: "Wait this many minutes after a loss", hint: "Needs trade times in your journal.", kind: "number", min: 5, max: 240, step: 5, example: 30 },
];

const STATUS: Record<string, { label: string; cls: string }> = {
  kept: { label: "Never broken", cls: "bg-emerald-500/15 text-emerald-300" },
  broken: { label: "Broken", cls: "bg-rose-500/15 text-rose-300" },
  needs_times: { label: "Needs trade times", cls: "bg-slate-500/20 text-slate-300" },
};

function RuleRow({ def, value, onChange }: { def: RuleDef; value: any; onChange: (v: any) => void }) {
  const on = value !== undefined && value !== null && value !== false;
  return (
    <li className="flex flex-wrap items-center gap-3 py-3">
      <input type="checkbox" checked={on} aria-label={`Use rule: ${def.label}`} className="h-4 w-4"
        onChange={(e) => onChange(e.target.checked ? (def.kind === "toggle" ? true : def.example) : null)} />
      <div className="min-w-0 flex-1">
        <div className={`text-sm ${on ? "text-slate-100" : "text-slate-400"}`}>{def.label}</div>
        <div className="text-[11px] text-slate-500">{def.hint}</div>
      </div>
      {def.kind === "number" && on && (
        <input type="number" min={def.min} max={def.max} step={def.step} value={value}
          aria-label={def.label} className={inputCls + " w-24 text-right tabular-nums"}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))} />
      )}
    </li>
  );
}

export default function RulesPage() {
  const [rules, setRules] = useState<Record<string, any> | null>(null);
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  const loadDiscipline = () => api("/api/parakh/rules/discipline").then(setD).catch((e) => setErr(e.message));
  useEffect(() => {
    api<any>("/api/parakh/rules").then((r) => setRules(r.rules)).catch((e) => setErr(e.message));
    loadDiscipline();
  }, []);

  const save = async () => {
    setBusy(true); setErr(""); setOk("");
    try {
      const body: Record<string, any> = {};
      for (const [k, v] of Object.entries(rules || {})) if (v !== null && v !== "" && v !== false) body[k] = v;
      setRules((await post<any>("/api/parakh/rules", body, "PUT")).rules);
      setOk("Saved.");
      await loadDiscipline();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  if (!rules) return err ? <ErrorBox message={err} /> : <Loading />;
  const set = (id: string) => (v: any) => { setOk(""); setRules({ ...rules, [id]: v }); };
  const title = (id: string) => d?.rules?.find((r: any) => r.id === id)?.title || id;

  return (
    <div className="space-y-4">
      <PageHeader title="My rules"
        subtitle="Write your own trading rules once. Parakh checks every new idea against them and counts how often you kept them. The rules are yours: Parakh does not tell you what they should be." />
      <ErrorBox message={err} />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Rules for a new idea">
          <ul className="divide-y divide-slate-800/70">
            {IDEA_RULES.map((def) => <RuleRow key={def.id} def={def} value={rules[def.id]} onChange={set(def.id)} />)}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">
            You see the result on every report in <Link href="/check" className="underline underline-offset-2">Check a trade</Link>.
          </p>
        </Card>
        <Card title="Rules for a trading day">
          <ul className="divide-y divide-slate-800/70">
            {DAY_RULES.map((def) => <RuleRow key={def.id} def={def} value={rules[def.id]} onChange={set(def.id)} />)}
          </ul>
          <p className="mt-2 text-[11px] text-slate-500">
            Checked against the trades in your <Link href="/journal" className="underline underline-offset-2">Journal</Link>.
          </p>
        </Card>
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={save} busy={busy}>Save my rules</Button>
        {ok && <span className="text-sm text-emerald-300">{ok}</span>}
      </div>

      <Card title="Discipline: did you keep your trading-day rules?">
        {!d ? <Loading /> : d.status === "no_rules" ? (
          <Empty>{d.message}</Empty>
        ) : (
          <div className="space-y-4">
            {d.status === "insufficient_data" ? (
              <div>
                <div className="text-sm text-amber-300">{d.message}</div>
                <div className="mt-2 h-2 max-w-sm overflow-hidden rounded-full bg-white/5">
                  <div className="h-full rounded-full bg-amber-400" style={{ width: `${Math.min(100, (100 * d.trading_days) / d.min_days)}%` }} />
                </div>
                <p className="mt-2 text-xs text-slate-500">No score is shown on too few days. Import more trades in the Journal.</p>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                <Stat label="Discipline score" value={`${d.score}/100`} hint="share of trading days with no rule broken"
                  tone={d.score >= 80 ? "good" : d.score < 50 ? "bad" : "neutral"} />
                <Stat label="Days rules kept" value={`${d.days_kept} of ${d.trading_days}`} />
                <div className="col-span-2 flex items-center text-lg font-semibold text-white sm:col-span-1">{d.headline}</div>
              </div>
            )}

            <ul className="divide-y divide-slate-800/70">
              {d.rules.map((r: any) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                  <div>
                    <div className="text-sm font-medium text-slate-200">{r.title}</div>
                    <div className="text-xs text-slate-400">
                      {r.status === "needs_times" ? "Your imported trades have dates but no times, so this cannot be checked."
                        : r.trades === 0 ? "No trade broke this rule."
                        : <>Broken by {r.trades} trade{r.trades === 1 ? "" : "s"} on {r.days_broken} day{r.days_broken === 1 ? "" : "s"}. Those trades together made <span className={r.net_pnl < 0 ? "text-rose-300" : "text-emerald-300"}>{inr(r.net_pnl, 0)}</span>.</>}
                    </div>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${STATUS[r.status]?.cls}`}>{STATUS[r.status]?.label}</span>
                </li>
              ))}
            </ul>

            {d.recent_days?.length > 0 && (
              <div>
                <div className="mb-1 text-xs font-medium text-slate-400">Last {d.recent_days.length} trading days</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-[11px] uppercase tracking-wide text-slate-500">
                      <tr><th className="py-1.5 pr-3">Date</th><th className="pr-3">Trades</th><th className="pr-3">Net P&amp;L</th><th>Rules broken</th></tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/70">
                      {d.recent_days.map((day: any) => (
                        <tr key={day.date}>
                          <td className="py-1.5 pr-3 tabular-nums text-slate-300">{day.date}</td>
                          <td className="pr-3 tabular-nums text-slate-300">{day.trades}</td>
                          <td className={`pr-3 tabular-nums ${day.net_pnl < 0 ? "text-rose-300" : "text-emerald-300"}`}>{inr(day.net_pnl, 0)}</td>
                          <td className={day.broken.length ? "text-rose-300" : "text-emerald-300"}>
                            {day.broken.length ? day.broken.map(title).join("; ") : "None"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            <p className="text-[11px] text-slate-500">{d.caveat}</p>
          </div>
        )}
      </Card>
    </div>
  );
}
