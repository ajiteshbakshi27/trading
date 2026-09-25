"use client";
import { useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { api } from "@/lib/api";

const COLORS = ["#22c55e", "#3b82f6", "#a855f7", "#f59e0b", "#ef4444", "#06b6d4", "#84cc16", "#f97316"];

export default function AllocatorPage() {
  const [budget, setBudget] = useState("100000");
  const [currency, setCurrency] = useState("INR");
  const [risk, setRisk] = useState("balanced");
  const [plan, setPlan] = useState<any>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [execLog, setExecLog] = useState<string[]>([]);
  const [buying, setBuying] = useState(""); // "" | "all" | symbol

  const run = async () => {
    const b = Number(budget);
    if (!Number.isFinite(b) || b <= 0) {
      setErr("Budget must be a positive number."); setPlan(null); return;
    }
    setLoading(true); setErr(""); setExecLog([]);
    try {
      const j = await api<any>("/api/allocate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget: b, currency, risk_profile: risk }),
      });
      setPlan(j);
    } catch (e: any) { setErr(e.message); setPlan(null); }
    finally { setLoading(false); }
  };

  const buyLine = async (symbol: string, qty: number) => {
    if (buying) return;
    setBuying(symbol);
    try {
      const j = await api<any>("/api/trade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, qty, side: "buy", order_type: "market" }),
      });
      setExecLog((l) => [...l, `${symbol} x${qty}: ${j.status}${j.error ? ` — ${j.error}` : ""}`]);
    } catch (e: any) {
      setExecLog((l) => [...l, `${symbol} x${qty}: ERROR — ${e.message}`]);
    } finally { setBuying(""); }
  };

  const buyAll = async () => {
    const longs = (plan?.lines || []).filter((l: any) => l.direction === "LONG" && l.shares > 0);
    for (const ln of longs) {
      await buyLine(ln.symbol, ln.shares);
    }
  };

  const longsBusy = buying !== "";
  const pie = plan ? [
    ...(plan.lines || []).filter((l: any) => l.direction === "LONG" && l.cost > 0)
      .map((l: any) => ({ name: l.symbol, value: l.cost })),
    { name: "Cash", value: plan.leftover_cash },
  ] : [];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">AI Capital Allocator & Profit Maximizer</h1>
      <div className="glass rounded-2xl p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm">Budget
            <input value={budget} onChange={(e) => setBudget(e.target.value)} type="number" min="1"
              className="ml-2 w-36 rounded-lg bg-black/40 px-3 py-1.5 outline-none" />
          </label>
          <label className="text-sm">Currency
            <select value={currency} onChange={(e) => setCurrency(e.target.value)}
              className="ml-2 rounded-lg bg-black/40 px-3 py-1.5">
              <option>INR</option><option>USD</option>
            </select>
          </label>
          <label className="text-sm">Risk
            <select value={risk} onChange={(e) => setRisk(e.target.value)}
              className="ml-2 rounded-lg bg-black/40 px-3 py-1.5">
              <option value="balanced">Balanced</option>
              <option value="aggressive">Aggressive Growth</option>
              <option value="conservative">Conservative</option>
              <option value="hft-arb">High-Frequency Arbitrage</option>
            </select>
          </label>
          <button onClick={run} disabled={loading}
            className="rounded-lg bg-green-500 px-4 py-1.5 text-sm font-bold text-black transition hover:bg-green-400 disabled:opacity-50">
            {loading ? "Optimizing…" : "Allocate"}
          </button>
        </div>
        {err && <p className="mt-2 text-sm text-red-400">{err}</p>}
        <p className="mt-2 text-xs text-slate-500">Estimates from quantum weights + sentiment momentum; not financial advice.</p>
      </div>

      {plan && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            {[[ "Invested", `${plan.currency} ${plan.long_cost.toLocaleString()} (${plan.invested_pct}%)`],
              ["Leftover Cash", `${plan.currency} ${plan.leftover_cash.toLocaleString()}`],
              ["Projected Return", `${plan.projected_return_pct}%`],
              ["Est. Drawdown", `${plan.estimated_drawdown_pct}%`]].map(([k, v]) => (
              <div key={k} className="glass rounded-2xl p-3">
                <div className="text-xs text-slate-400">{k}</div>
                <div className="text-lg font-bold">{v}</div>
              </div>
            ))}
          </div>
          {plan.costs && (
            <div className="glass rounded-2xl p-3 text-sm text-slate-300">
              <span className="font-semibold text-white">Net-profit check:</span>{" "}
              fees {plan.currency} {plan.costs.fee} · slippage {plan.costs.slippage} ·{" "}
              est. tax {plan.costs.est_tax_on_profit} → net projected{" "}
              <b className={plan.net_projected_return_pct >= 0 ? "text-emerald-400" : "text-rose-400"}>
                {plan.net_projected_return_pct}%
              </b>
            </div>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="glass rounded-2xl p-4">
              <h2 className="mb-2 font-semibold">Allocation Mix</h2>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={pie} dataKey="value" nameKey="name" outerRadius={90} label>
                      {pie.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="glass rounded-2xl p-4">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="font-semibold">Buy Orders</h2>
                <button onClick={buyAll} disabled={longsBusy}
                  className="rounded-lg bg-blue-500 px-3 py-1 text-xs font-bold text-white transition hover:bg-blue-400 disabled:opacity-50">
                  {buying === "all" ? "Executing…" : longsBusy ? "Waiting…" : "Buy all longs"}
                </button>
              </div>
              <div className="space-y-2">
                {plan.lines.map((l: any) => (
                  <div key={l.symbol + l.direction}
                    className={`flex items-center justify-between rounded-xl p-2 text-sm ${l.direction === "LONG" ? "bg-emerald-500/10" : "bg-rose-500/10"}`}>
                    <div>
                      <span className="font-bold">{l.symbol}</span>{" "}
                      <span className={`rounded px-1.5 py-0.5 text-xs ${l.direction === "LONG" ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                        {l.direction === "LONG" ? `BUY ${l.shares}` : `HEDGE ${l.shares} (${l.notional})`}
                      </span>
                      <div className="text-xs text-slate-400">Tgt {l.target} · {l.type.replace("_", " ")}</div>
                    </div>
                    {l.direction === "LONG" && l.shares > 0 && (
                      <button onClick={() => buyLine(l.symbol, l.shares)} disabled={longsBusy}
                        className="rounded-lg bg-green-500 px-3 py-1 text-xs font-bold text-black transition hover:bg-green-400 disabled:opacity-50">
                        {buying === l.symbol ? "…" : "Buy"}
                      </button>
                    )}
                  </div>
                ))}
              </div>
              {execLog.length > 0 && (
                <div className="mt-2 rounded-lg bg-black/40 p-2 text-xs">
                  {execLog.map((m, i) => <div key={i} className={m.includes("ERROR") ? "text-rose-400" : ""}>{m}</div>)}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
