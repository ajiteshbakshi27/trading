"use client";
import { useState } from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { api } from "@/lib/api";

const PERIODS = [30, 90, 365];

export default function QuantumPage() {
  const [res, setRes] = useState<any>(null);
  const [resBusy, setResBusy] = useState(false);
  const [resErr, setResErr] = useState("");
  const [bt, setBt] = useState<any>(null);
  const [btBusy, setBtBusy] = useState(false);
  const [btErr, setBtErr] = useState("");
  const [period, setPeriod] = useState(90);
  const [holdings, setHoldings] = useState('{"NVDA": 20, "AAPL": 1}');
  const [reb, setReb] = useState<any>(null);
  const [rebErr, setRebErr] = useState("");
  const [rebBusy, setRebBusy] = useState(false);
  const [execBusy, setExecBusy] = useState("");

  const runOpt = async () => {
    if (resBusy) return;
    setResBusy(true); setResErr("");
    const body = {
      symbols: ["NVDA","AAPL","MSFT","TSLA"],
      expected_returns: [0.14, 0.08, 0.10, 0.16],
      cov_matrix: [[0.09,0.02,0.03,0.04],[0.02,0.04,0.02,0.01],[0.03,0.02,0.05,0.02],[0.04,0.01,0.02,0.12]],
      risk_aversion: 1.0
    };
    try {
      setRes(await api<any>("/api/quantum/optimize", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      }));
    } catch (e: any) { setResErr(e.message || "Optimization failed"); setRes(null); }
    finally { setResBusy(false); }
  };

  const runBt = async (p: number) => {
    if (btBusy) return;
    setPeriod(p); setBtBusy(true); setBtErr("");
    try {
      setBt(await api<any>(`/api/backtest?symbol=NVDA&periods=${p}&series=true`));
    } catch (e: any) { setBtErr(e.message || "Backtest failed"); setBt(null); }
    finally { setBtBusy(false); }
  };

  const runReb = async () => {
    if (rebBusy) return;
    setRebErr("");
    let parsed: any;
    try { parsed = JSON.parse(holdings || "{}"); }
    catch { setRebErr("Holdings must be valid JSON, e.g. {\"NVDA\": 20}"); return; }
    setRebBusy(true);
    try {
      const j = await api<any>("/api/rebalance", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ holdings: parsed }),
      });
      setReb(j);
    } catch (e: any) { setRebErr(e.message || "Rebalance failed"); setReb(null); }
    finally { setRebBusy(false); }
  };

  const execOrder = async (o: any) => {
    if (execBusy) return;
    setExecBusy(o.symbol);
    try {
      const j = await api<any>("/api/trade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: o.symbol, qty: o.qty, side: o.side, order_type: "market" }),
      });
      setExecBusy("");
      return j.status !== "ERROR";
    } catch {
      setExecBusy("");
      return false;
    }
  };

  const series = bt?.series && bt.series.hft_quantum && bt.series.sentiment_contrarian && bt.series.buy_hold
    ? Object.keys(bt.series.hft_quantum).map((i) => ({
        i: Number(i),
        "Quantum+HFT": bt.series.hft_quantum[i],
        "Sentiment": bt.series.sentiment_contrarian[i],
        "Buy&Hold": bt.series.buy_hold[i],
      }))
    : [];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Quantum VQE / QAOA Analytics</h1>

      <div className="glass rounded-2xl p-4">
        <p className="text-sm text-slate-400">QAOA portfolio selection (PennyLane, p=2 layers). Falls back to classical min-variance when quantum unavailable or n&gt;8.</p>
        <button onClick={runOpt} disabled={resBusy}
          className="mt-3 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-bold text-black transition hover:bg-emerald-400 disabled:opacity-50">
          {resBusy ? "Optimizing…" : "Run Quantum Optimization"}
        </button>
        {resErr && <p className="mt-2 text-sm text-rose-400">{resErr}</p>}
        {res && <pre className="mt-3 overflow-auto rounded-lg bg-black/40 p-3 text-xs">{JSON.stringify(res, null, 2)}</pre>}
      </div>

      <div className="glass rounded-2xl p-4">
        <h2 className="font-semibold">Backtest: Quantum+Sentiment vs HFT vs Buy&amp;Hold</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {PERIODS.map((p) => (
            <button key={p} onClick={() => runBt(p)} disabled={btBusy}
              className={`rounded-lg px-3 py-1 text-sm disabled:opacity-50 ${
                p === period && bt ? "bg-emerald-500 text-black" : "glass"}`}>
              {p}d
            </button>
          ))}
        </div>
        {btErr && <p className="mt-2 text-sm text-rose-400">{btErr}</p>}
        {!bt && !btErr && !btBusy && (
          <p className="mt-2 text-sm text-slate-500">Pick a period to run the backtest.</p>
        )}
        {btBusy && <p className="mt-2 text-sm text-slate-400">Running backtest…</p>}
        {bt && !btBusy && (
          <>
            <div className="mt-2 text-sm text-slate-300">
              Winner: <b>{bt.winner}</b> ·
              {Object.entries(bt.strategies).map(([k, v]: any) => (
                <span key={k} className="ml-3">{k}: {v.return_pct}% (Sharpe {v.sharpe}, DD {v.max_dd_pct}%)</span>
              ))}
            </div>
            {series.length ? (
              <div className="mt-2 h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={series}>
                    <XAxis dataKey="i" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={["auto", "auto"]} />
                    <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
                    <Legend />
                    <Line type="monotone" dataKey="Quantum+HFT" stroke="#22C55E" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="Sentiment" stroke="#a855f7" dot={false} />
                    <Line type="monotone" dataKey="Buy&Hold" stroke="#64748b" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="mt-2 text-xs text-slate-500">No equity-curve series in this response.</p>
            )}
          </>
        )}
      </div>

      <div className="glass rounded-2xl p-4">
        <h2 className="font-semibold">Portfolio Rebalancer (drift → orders)</h2>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input value={holdings} onChange={(e) => setHoldings(e.target.value)}
            className="w-64 rounded-lg bg-black/40 px-3 py-1.5 text-sm outline-none" placeholder='{"NVDA": 20}' />
          <button onClick={runReb} disabled={rebBusy}
            className="rounded-lg bg-blue-500 px-4 py-1.5 text-sm font-bold text-white transition hover:bg-blue-400 disabled:opacity-50">
            {rebBusy ? "Calculating…" : "Rebalance Portfolio"}
          </button>
        </div>
        {rebErr && <p className="mt-2 text-sm text-rose-400">{rebErr}</p>}
        {reb && (
          <div className="mt-2 text-sm">
            <div className="text-slate-300">Value {reb.total_value} · {reb.n_orders} orders</div>
            {reb.orders.map((o: any, i: number) => (
              <div key={i} className="mt-1 flex items-center justify-between rounded-lg bg-white/5 p-2">
                <span>
                  <b className={o.side === "buy" ? "text-emerald-400" : "text-rose-400"}>{o.side.toUpperCase()}</b> {o.qty} {o.symbol} ({o.notional})
                </span>
                <button onClick={() => execOrder(o)} disabled={!!execBusy}
                  className={`rounded-lg px-3 py-1 text-xs font-bold disabled:opacity-50 ${
                    o.side === "buy" ? "bg-emerald-500 text-black hover:bg-emerald-400" : "bg-rose-500 text-white hover:bg-rose-400"}`}>
                  {execBusy === o.symbol ? "…" : "Execute"}
                </button>
              </div>
            ))}
            {!reb.orders.length && <div className="mt-1 text-slate-400">No drift ≥ 1 share — nothing to do.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
