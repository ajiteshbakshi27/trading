"use client";
import { useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { post } from "@/lib/api";
import { Button, Card, ErrorBox, Field, PageHeader, Stat, inputCls, inr } from "@/components/parakh/ui";

type Leg = { kind: string; side: string; strike: string; premium: string; lots: string };
const PRESETS: Record<string, (s: number) => Leg[]> = {
  "Long call": (s) => [{ kind: "CE", side: "BUY", strike: String(s), premium: "", lots: "1" }],
  "Bull call spread": (s) => [{ kind: "CE", side: "BUY", strike: String(s), premium: "", lots: "1" }, { kind: "CE", side: "SELL", strike: String(s + 200), premium: "", lots: "1" }],
  "Short straddle": (s) => [{ kind: "CE", side: "SELL", strike: String(s), premium: "", lots: "1" }, { kind: "PE", side: "SELL", strike: String(s), premium: "", lots: "1" }],
  "Iron condor": (s) => [
    { kind: "PE", side: "BUY", strike: String(s - 400), premium: "", lots: "1" }, { kind: "PE", side: "SELL", strike: String(s - 200), premium: "", lots: "1" },
    { kind: "CE", side: "SELL", strike: String(s + 200), premium: "", lots: "1" }, { kind: "CE", side: "BUY", strike: String(s + 400), premium: "", lots: "1" }],
};

export default function OptionsPage() {
  const [und, setUnd] = useState("NIFTY");
  const [spot, setSpot] = useState("24000");
  const [dte, setDte] = useState("7");
  const [lot, setLot] = useState("");
  const [legs, setLegs] = useState<Leg[]>(PRESETS["Bull call spread"](24000));
  const [r, setR] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const upd = (i: number, k: keyof Leg, v: string) => setLegs(legs.map((l, j) => (j === i ? { ...l, [k]: v } : l)));
  const run = async () => {
    setBusy(true); setErr("");
    try {
      setR(await post("/api/parakh/options/analyse", {
        underlying: und, spot: spot ? Number(spot) : undefined, days_to_expiry: Number(dte), lot_size: lot ? Number(lot) : undefined,
        legs: legs.map((l) => ({ kind: l.kind, side: l.side, strike: l.strike ? Number(l.strike) : undefined, premium: l.premium ? Number(l.premium) : undefined, lots: Number(l.lots || 1) })),
      }));
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="F&O analyser" subtitle="See the payoff, breakevens, worst case and real probability of profit before you place an options trade." />
      <Card>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Field label="Underlying"><select className={inputCls} value={und} onChange={(e) => setUnd(e.target.value)}>{["NIFTY", "BANKNIFTY", "FINNIFTY", "SENSEX"].map((u) => <option key={u}>{u}</option>)}</select></Field>
          <Field label="Spot ₹" hint="blank = last close"><input className={inputCls} type="number" value={spot} onChange={(e) => setSpot(e.target.value)} /></Field>
          <Field label="Days to expiry"><input className={inputCls} type="number" min={0} value={dte} onChange={(e) => setDte(e.target.value)} /></Field>
          <Field label="Lot size" hint="blank = default; confirm with NSE"><input className={inputCls} type="number" value={lot} onChange={(e) => setLot(e.target.value)} /></Field>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {Object.keys(PRESETS).map((p) => <button key={p} onClick={() => setLegs(PRESETS[p](Math.round(Number(spot || 24000) / 50) * 50))} className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10">{p}</button>)}
        </div>
        <div className="mt-3 space-y-2">
          {legs.map((l, i) => (
            <div key={i} className="grid grid-cols-6 gap-2">
              <select className={inputCls} value={l.side} onChange={(e) => upd(i, "side", e.target.value)} aria-label="Buy or sell"><option>BUY</option><option>SELL</option></select>
              <select className={inputCls} value={l.kind} onChange={(e) => upd(i, "kind", e.target.value)} aria-label="Instrument"><option>CE</option><option>PE</option><option>FUT</option></select>
              <input className={inputCls} type="number" placeholder="Strike" value={l.strike} onChange={(e) => upd(i, "strike", e.target.value)} aria-label="Strike" />
              <input className={inputCls} type="number" placeholder="Premium (auto)" value={l.premium} onChange={(e) => upd(i, "premium", e.target.value)} aria-label="Premium" />
              <input className={inputCls} type="number" min={1} placeholder="Lots" value={l.lots} onChange={(e) => upd(i, "lots", e.target.value)} aria-label="Lots" />
              <button onClick={() => setLegs(legs.filter((_, j) => j !== i))} className="text-xs text-slate-400 underline">remove</button>
            </div>
          ))}
          <button onClick={() => setLegs([...legs, { kind: "CE", side: "BUY", strike: spot, premium: "", lots: "1" }])} className="text-xs text-sky-300 underline">+ add leg</button>
        </div>
        <div className="mt-4"><Button onClick={run} busy={busy}>Analyse</Button></div>
        <p className="mt-2 text-[11px] text-slate-500">Leave premium blank to price with Black-Scholes at 15% IV, or enter the market premium to back out its implied volatility.</p>
      </Card>
      <ErrorBox message={err} />
      {r && (
        <>
          {r.warnings.length > 0 && <div className="space-y-1 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{r.warnings.map((w: string) => <p key={w}>⚠ {w}</p>)}</div>}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
            <Stat label={r.position_type === "credit" ? "Net credit" : "Net debit"} value={inr(Math.abs(r.net_premium), 0)} />
            <Stat label="Max profit" value={r.max_profit == null ? "Unlimited" : inr(r.max_profit, 0)} tone="good" />
            <Stat label="Max loss" value={r.max_loss == null ? "Unlimited" : inr(r.max_loss, 0)} tone="bad" />
            <Stat label="Prob. of profit" value={`${Math.round(r.probability_of_profit * 100)}%`} hint="at expiry, model-based" />
            <Stat label="Breakeven(s)" value={r.breakevens.map((b: number) => b.toFixed(0)).join(" / ") || "—"} hint={`±1σ move ${inr(r.expected_move_1sd, 0)}`} />
          </div>
          <Card title="Payoff at expiry">
            <div className="h-72">
              <ResponsiveContainer>
                <AreaChart data={r.payoff} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                  <defs><linearGradient id="pl" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#34d399" stopOpacity={0.4} /><stop offset="100%" stopColor="#34d399" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke="#1e293b" />
                  <XAxis dataKey="spot" type="number" domain={["dataMin", "dataMax"]} stroke="#64748b" fontSize={11} tickFormatter={(v) => v.toFixed(0)} />
                  <YAxis stroke="#64748b" fontSize={11} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} formatter={(v: any) => inr(v, 0)} labelFormatter={(l) => `Spot ${Number(l).toFixed(0)}`} />
                  <ReferenceLine y={0} stroke="#475569" /><ReferenceLine x={r.spot} stroke="#38bdf8" strokeDasharray="4 4" />
                  <Area dataKey="pnl" stroke="#34d399" fill="url(#pl)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card title="Net greeks">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 text-sm">
              {Object.entries(r.net_greeks).map(([k, v]: any) => <Stat key={k} label={k.replace(/_/g, " ")} value={Number(v).toFixed(k === "gamma" ? 4 : 2)} />)}
            </div>
            <p className="mt-2 text-[11px] text-slate-500">{r.assumptions}</p>
          </Card>
        </>
      )}
    </div>
  );
}
