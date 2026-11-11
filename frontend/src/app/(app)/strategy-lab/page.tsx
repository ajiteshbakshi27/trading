"use client";
import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { post } from "@/lib/api";
import { Button, Card, DataModeTag, ErrorBox, Field, PageHeader, Stat, inputCls, signedPct } from "@/components/parakh/ui";

const RULES: Record<string, { label: string; params: [string, string, number][] }> = {
  sma_cross_up: { label: "Fast average crosses above slow average", params: [["fast", "Fast SMA", 20], ["slow", "Slow SMA", 50]] },
  rsi_below: { label: "RSI dips below a level (buy the dip)", params: [["level", "RSI level", 30]] },
  breakout: { label: "Close above N-day high (breakout)", params: [["lookback", "Lookback days", 55]] },
  price_above_sma: { label: "Close crosses above an average", params: [["period", "SMA period", 50]] },
};

export default function StrategyLab() {
  const [symbol, setSymbol] = useState("RELIANCE");
  const [rule, setRule] = useState("sma_cross_up");
  const [params, setParams] = useState<Record<string, number>>({ fast: 20, slow: 50 });
  const [exit, setExit] = useState<Record<string, string>>({ stop_pct: "5", target_pct: "10", max_hold_days: "30" });
  const [years, setYears] = useState(3);
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const pickRule = (k: string) => { setRule(k); setParams(Object.fromEntries(RULES[k].params.map(([p, , d]) => [p, d]))); };
  const run = async () => {
    setBusy(true); setErr("");
    try {
      const exit_params = Object.fromEntries(Object.entries(exit).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]));
      setR(await post("/api/parakh/backtest", { symbol, entry_rule: rule, entry_params: params, exit_params, years }));
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Strategy backtests" subtitle="Test a simple rule on real NSE history — with the honesty checks: next-day fills, costs, out-of-sample and overfitting warnings." />
      <Card>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="NSE symbol"><input className={inputCls} value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /></Field>
          <Field label="Entry rule"><select className={inputCls} value={rule} onChange={(e) => pickRule(e.target.value)}>{Object.entries(RULES).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}</select></Field>
          <Field label="Years of history"><select className={inputCls} value={years} onChange={(e) => setYears(Number(e.target.value))}>{[1, 2, 3, 4, 5].map((y) => <option key={y}>{y}</option>)}</select></Field>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-6">
          {RULES[rule].params.map(([p, label]) => (
            <Field key={p} label={label}><input type="number" className={inputCls} value={params[p] ?? ""} onChange={(e) => setParams({ ...params, [p]: Number(e.target.value) })} /></Field>
          ))}
          <Field label="Stop %"><input type="number" className={inputCls} value={exit.stop_pct} onChange={(e) => setExit({ ...exit, stop_pct: e.target.value })} /></Field>
          <Field label="Target %"><input type="number" className={inputCls} value={exit.target_pct} onChange={(e) => setExit({ ...exit, target_pct: e.target.value })} /></Field>
          <Field label="Max days"><input type="number" className={inputCls} value={exit.max_hold_days} onChange={(e) => setExit({ ...exit, max_hold_days: e.target.value })} /></Field>
        </div>
        <div className="mt-4"><Button onClick={run} busy={busy}>Run backtest</Button></div>
      </Card>
      <ErrorBox message={err} />
      {r && (
        <>
          {r.warnings.length > 0 && <div className="space-y-1 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{r.warnings.map((w: string) => <p key={w}>⚠ {w}</p>)}</div>}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
            <Stat label="Total return" value={signedPct(r.full.total_return_pct)} tone={r.full.total_return_pct >= 0 ? "good" : "bad"} hint={`buy & hold ${signedPct(r.full.buy_hold_return_pct)}`} />
            <Stat label="Trades" value={r.full.trades} />
            <Stat label="Win rate" value={r.full.win_rate == null ? "—" : `${Math.round(r.full.win_rate * 100)}%`} />
            <Stat label="Max drawdown" value={`-${r.full.max_drawdown_pct}%`} tone="bad" />
            <Stat label="Sharpe" value={r.full.sharpe} />
            <Stat label="Out-of-sample" value={signedPct(r.out_of_sample.total_return_pct)} hint={`${r.out_of_sample.trades} trades, last 30%`} />
          </div>
          <Card title={<span className="flex items-center gap-2">Equity curve <DataModeTag mode={r.data_mode} /></span>}>
            <div className="h-64">
              <ResponsiveContainer>
                <LineChart data={r.full.equity_curve} margin={{ top: 8, right: 8, bottom: 8, left: -12 }}>
                  <CartesianGrid stroke="#1e293b" /><XAxis dataKey="date" stroke="#64748b" fontSize={11} minTickGap={40} /><YAxis stroke="#64748b" fontSize={11} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                  <Line dataKey="equity" stroke="#34d399" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Parameter sensitivity (±20%)">
            <ul className="text-sm text-slate-300">{r.sensitivity.map((s: any, i: number) => <li key={i}>{JSON.stringify(s.params)} → {signedPct(s.total_return_pct)} ({s.trades} trades)</li>)}</ul>
            <p className="mt-2 text-[11px] text-slate-500">{r.method} Round-trip cost {r.cost_pct_round_trip}%.</p>
          </Card>
        </>
      )}
    </div>
  );
}
