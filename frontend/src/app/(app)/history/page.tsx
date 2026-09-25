"use client";
import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

const TABS = ["Signals", "Predictions", "Trades"] as const;

export default function HistoryPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Signals");
  const [signals, setSignals] = useState<any[]>([]);
  const [preds, setPreds] = useState<any[]>([]);
  const [trades, setTrades] = useState<any[]>([]);
  const [symbol, setSymbol] = useState("");
  const [backend, setBackend] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const q = symbol ? `&symbol=${symbol.toUpperCase()}` : "";
      const [h, t] = await Promise.all([
        api<any>(`/api/history?limit=100${q}`),
        api<any>(`/api/trades?limit=100${q}`),
      ]);
      setSignals(h.signals || []);
      setPreds(h.predictions || []);
      setTrades(t.trades || []);
      setBackend(h.backend || "");
    } catch (e: any) {
      setError(e.message || "Failed to load history");
    } finally { setLoading(false); }
  }, [symbol]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">History</h1>
        <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-xs text-slate-400">
          {backend ? `db: ${backend}` : "db: …"}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value)}
            placeholder="Filter symbol (e.g. NVDA)"
            className="w-44 rounded-lg bg-black/40 px-3 py-1.5 text-sm outline-none" />
          <button onClick={load} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-bold text-black hover:bg-emerald-400 disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="flex gap-1.5">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-1 text-sm ${tab === t ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>
            {t}
          </button>
        ))}
      </div>

      {error && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-300">{error}</p>}

      {loading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : tab === "Signals" ? (
        <div className="glass overflow-auto rounded-2xl p-4">
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr><th className="text-left">Time</th><th className="text-left">Symbol</th><th>Type</th><th>Dir</th><th>Conf</th><th>Price</th><th>Target</th><th>Stop</th><th className="text-left">Rationale</th></tr>
            </thead>
            <tbody>
              {signals.map((s) => (
                <tr key={s.id} className="border-t border-white/5">
                  <td className="tnum py-1.5 text-xs text-slate-500">{new Date(s.created_at).toLocaleTimeString()}</td>
                  <td className="font-semibold">{s.symbol}</td>
                  <td className={s.signal_type === "BET_AGAINST" ? "text-rose-300" : s.signal_type === "BET_FOR" ? "text-emerald-300" : "text-slate-400"}>{s.signal_type}</td>
                  <td>{s.direction}</td>
                  <td className="tnum">{(s.confidence * 100).toFixed(0)}%</td>
                  <td className="tnum">${s.price}</td>
                  <td className="tnum">${s.target}</td>
                  <td className="tnum">${s.stop}</td>
                  <td className="max-w-xs truncate text-xs text-slate-400">{s.rationale}</td>
                </tr>
              ))}
              {!signals.length && <tr><td colSpan={9} className="py-6 text-center text-slate-500">No stored signals yet — they persist as the dashboard streams.</td></tr>}
            </tbody>
          </table>
        </div>
      ) : tab === "Predictions" ? (
        <div className="glass overflow-auto rounded-2xl p-4">
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr><th className="text-left">Time</th><th className="text-left">Market</th><th>Crowd</th><th>Quantum</th><th>Edge</th><th>Side</th><th>Conf</th></tr>
            </thead>
            <tbody>
              {preds.map((p) => (
                <tr key={p.id} className="border-t border-white/5">
                  <td className="tnum py-1.5 text-xs text-slate-500">{new Date(p.created_at).toLocaleTimeString()}</td>
                  <td className="max-w-sm truncate">{p.question}</td>
                  <td className="tnum">{(p.crowd_prob * 100).toFixed(1)}%</td>
                  <td className="tnum">{(p.quantum_prob * 100).toFixed(1)}%</td>
                  <td className={`tnum font-semibold ${p.edge > 0 ? "text-emerald-300" : "text-rose-300"}`}>
                    {p.edge > 0 ? "+" : ""}{(p.edge * 100).toFixed(1)}pp</td>
                  <td>{p.side}</td>
                  <td className="tnum">{(p.confidence * 100).toFixed(0)}%</td>
                </tr>
              ))}
              {!preds.length && <tr><td colSpan={7} className="py-6 text-center text-slate-500">No stored predictions yet.</td></tr>}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="glass overflow-auto rounded-2xl p-4">
          <table className="w-full text-sm">
            <thead className="text-slate-400">
              <tr><th className="text-left">Time</th><th className="text-left">Symbol</th><th>Side</th><th>Qty</th><th>Type</th><th>Status</th><th className="text-left">Detail</th></tr>
            </thead>
            <tbody>
              {trades.map((t) => (
                <tr key={t.id} className="border-t border-white/5">
                  <td className="tnum py-1.5 text-xs text-slate-500">{new Date(t.created_at).toLocaleTimeString()}</td>
                  <td className="font-semibold">{t.symbol}</td>
                  <td className={t.side === "buy" ? "text-emerald-300" : "text-rose-300"}>{t.side}</td>
                  <td className="tnum">{t.qty}</td>
                  <td>{t.order_type}</td>
                  <td><span className={`rounded px-1.5 py-0.5 text-xs ${t.status === "ERROR" ? "bg-rose-500/15 text-rose-300" : t.status === "MOCK_FILLED" ? "bg-amber-500/15 text-amber-300" : "bg-emerald-500/15 text-emerald-300"}`}>{t.status}</span></td>
                  <td className="max-w-xs truncate text-xs text-slate-400">{t.detail}</td>
                </tr>
              ))}
              {!trades.length && <tr><td colSpan={7} className="py-6 text-center text-slate-500">No orders routed yet — try Buy on a signal card or the allocator.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
