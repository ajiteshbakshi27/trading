"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import { api } from "@/lib/api";

type Portfolio = {
  initial_cash: number;
  cash: number;
  invested: number;
  market_value: number;
  equity: number;
  realized_pnl: number;
  total_pnl: number;
  total_pnl_pct: number;
  sharpe: number | null;
  max_drawdown_pct: number;
  positions: Array<{
    symbol: string;
    qty: number;
    avg_entry: number;
    realized_pnl: number;
  }>;
  position_count: number;
  data_mode: string;
};

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [order, setOrder] = useState({ symbol: "NVDA", qty: 10, side: "buy", price: 130 });
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await api<any>("/api/paper/portfolio");
      setPortfolio(res);
      setError("");
    } catch (e: any) {
      setError(e.message || "Failed to load portfolio");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const placeOrder = async () => {
    setMsg("");
    try {
      const res = await api<any>("/api/paper/order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(order),
      });
      setPortfolio(res.portfolio);
      setMsg(`Order filled: ${order.side} ${order.qty} ${order.symbol} @ ${order.price}`);
    } catch (e: any) {
      setMsg(e.message || "Order failed");
    }
  };

  const deployAllocator = async () => {
    setMsg("");
    try {
      const res = await api<any>("/api/paper/allocator", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ budget: 100000, risk_profile: "balanced" }),
      });
      setPortfolio(res.portfolio);
      setMsg(`Allocator deployed ${res.orders.length} order(s)`);
    } catch (e: any) {
      setMsg(e.message || "Allocator deploy failed");
    }
  };

  const liquidate = async () => {
    if (!confirm("Liquidate all positions?")) return;
    setMsg("");
    try {
      const res = await api<any>("/api/paper/liquidate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "manual",
      });
      setPortfolio(res.portfolio);
      setMsg(`Liquidated ${res.orders.length} position(s)`);
    } catch (e: any) {
      setMsg(e.message || "Liquidation failed");
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Trading</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Virtual Portfolio</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Paper trading ledger. Deploy allocator plans, execute orders, and
            track P&L — all simulated.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="rounded-full bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
          >
            Refresh
          </button>
          <DataModeBadge mode={portfolio?.data_mode ?? "mock"} />
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : !portfolio ? (
        <div className="space-y-4">
          <div className="h-8 w-64 animate-pulse rounded bg-white/5" />
          <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
        </div>
      ) : (
        <>
          <SectionCard title="Account" subtitle="Virtual ₹10,000 ledger">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Equity</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  ₹{portfolio.equity.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Cash</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  ₹{portfolio.cash.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Invested</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  ₹{portfolio.invested.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Total P&L</div>
                <div className={`mt-1 text-xl font-bold tabular-nums ${portfolio.total_pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                  {portfolio.total_pnl >= 0 ? "+" : ""}₹{portfolio.total_pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                </div>
                <div className="text-[10px] tabular-nums text-slate-500">
                  {portfolio.total_pnl_pct >= 0 ? "+" : ""}{portfolio.total_pnl_pct.toFixed(2)}%
                </div>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Sharpe</div>
                <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                  {portfolio.sharpe != null ? portfolio.sharpe.toFixed(2) : "—"}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Max drawdown</div>
                <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
                  {portfolio.max_drawdown_pct.toFixed(2)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Positions</div>
                <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                  {portfolio.position_count}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Positions" subtitle="Current holdings">
            {portfolio.positions.length === 0 ? (
              <p className="text-sm text-slate-500">No open positions.</p>
            ) : (
              <div className="space-y-2">
                {portfolio.positions.map((p) => (
                  <div key={p.symbol} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
                    <span className="font-semibold text-slate-200">{p.symbol}</span>
                    <span className="tabular-nums text-slate-400">{p.qty} @ ₹{p.avg_entry.toFixed(2)}</span>
                    <span className="tabular-nums text-slate-500">
                      ₹{(p.qty * p.avg_entry).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </span>
                    <span className={`tabular-nums ${p.realized_pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {p.realized_pnl >= 0 ? "+" : ""}₹{p.realized_pnl.toFixed(0)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Execute order" subtitle="Paper order — no real money">
            <div className="flex flex-wrap items-end gap-3">
              <label className="text-xs text-slate-400">
                Symbol
                <input
                  value={order.symbol}
                  onChange={(e) => setOrder({ ...order, symbol: e.target.value.toUpperCase() })}
                  className="ml-2 rounded-lg border border-slate-700 bg-black/30 px-2 py-1 text-sm text-slate-200"
                />
              </label>
              <label className="text-xs text-slate-400">
                Side
                <select
                  value={order.side}
                  onChange={(e) => setOrder({ ...order, side: e.target.value })}
                  className="ml-2 rounded-lg border border-slate-700 bg-black/30 px-2 py-1 text-sm text-slate-200"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </label>
              <label className="text-xs text-slate-400">
                Qty
                <input
                  type="number"
                  value={order.qty}
                  onChange={(e) => setOrder({ ...order, qty: Number(e.target.value) })}
                  className="ml-2 w-20 rounded-lg border border-slate-700 bg-black/30 px-2 py-1 text-sm text-slate-200"
                />
              </label>
              <label className="text-xs text-slate-400">
                Price
                <input
                  type="number"
                  value={order.price}
                  onChange={(e) => setOrder({ ...order, price: Number(e.target.value) })}
                  className="ml-2 w-24 rounded-lg border border-slate-700 bg-black/30 px-2 py-1 text-sm text-slate-200"
                />
              </label>
              <button
                onClick={placeOrder}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-black hover:bg-emerald-400"
              >
                Place order
              </button>
            </div>
          </SectionCard>

          <SectionCard title="Allocator" subtitle="Deploy the smart allocator as paper orders">
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={deployAllocator}
                className="rounded-lg bg-cyan-500 px-4 py-2 text-xs font-bold text-black hover:bg-cyan-400"
              >
                Deploy allocator
              </button>
              <button
                onClick={liquidate}
                className="rounded-lg bg-rose-600 px-4 py-2 text-xs font-bold text-white hover:bg-rose-500"
              >
                Liquidate all
              </button>
              {msg ? <span className="text-xs text-slate-400">{msg}</span> : null}
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
