"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import { api } from "@/lib/api";
import { INSUFFICIENT_DATA, REGIME_LABELS, fmtPct } from "@/lib/research";

const SYMBOLS = ["NVDA", "TSLA", "AAPL", "AMD", "MSFT", "GOOGL", "META", "INTC", "AMZN"];
const PERIODS = ["6mo", "1y", "2y"];

type BacktestResult = {
  status: string;
  label: string;
  symbol: string;
  period: string;
  source: string;
  n_days: number;
  n_resolved: number;
  required: number;
  accuracy: number | null;
  mean_error_pct: number | null;
  mean_confidence: number | null;
  brier_score: number | null;
  regime_distribution: Record<string, number>;
  by_regime: Array<{ regime: string; n: number; accuracy: number; mean_error_pct: number }>;
  failure_categories: Array<{ failure_mode: string; count: number; share: number; mean_error_pct: number }>;
  data_mode: string;
  note: string;
  predictions: Array<{
    day_index: number;
    direction: string;
    confidence: number;
    expected_move_pct: number;
    actual_move_pct: number;
    signed_move_pct: number;
    correct: boolean;
    regime: string;
    error_pct: number;
    autopsy?: { failure_mode: string; mode_likelihood: number; regime_mismatch: boolean };
  }>;
};

export default function BacktestPage() {
  const [symbol, setSymbol] = useState("NVDA");
  const [period, setPeriod] = useState("1y");
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const run = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api<any>(
        `/api/backtest/research?symbol=${symbol}&period=${period}&min_resolved=20`
      );
      setResult(res.result);
    } catch (e: any) {
      setError(e.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  }, [symbol, period]);

  useEffect(() => {
    run();
  }, [run]);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Research</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Backtest Lab</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Replay the closed loop over a historical window and measure what
            actually happened.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={run}
            disabled={loading}
            className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-bold text-black hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Running…" : "Run backtest"}
          </button>
          <DataModeBadge mode={result?.data_mode ?? "backtest"} />
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-1">
          {SYMBOLS.map((s) => (
            <button
              key={s}
              onClick={() => setSymbol(s)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                s === symbol ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                p === period ? "bg-cyan-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : !result ? (
        <div className="space-y-4">
          <div className="h-8 w-64 animate-pulse rounded bg-white/5" />
          <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
        </div>
      ) : result.status === "insufficient_data" ? (
        <SectionCard title={`${result.symbol} — backtest`} subtitle={result.note}>
          <div className="rounded-xl border border-dashed border-slate-700 p-8 text-center">
            <p className="text-sm font-semibold text-rose-300">{INSUFFICIENT_DATA}</p>
            <p className="mt-1 text-xs text-slate-500">
              {result.n_resolved} resolved predictions / {result.required} required.
              Try a longer period or a different symbol.
            </p>
          </div>
        </SectionCard>
      ) : (
        <>
          <SectionCard
            title={`${result.symbol} — measured results`}
            subtitle={`${result.source} · ${result.n_days} trading days · ${result.n_resolved} resolved`}
          >
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Accuracy</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {result.accuracy != null ? `${(result.accuracy * 100).toFixed(1)}%` : "—"}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Mean error</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {result.mean_error_pct != null ? `${result.mean_error_pct.toFixed(2)}pp` : "—"}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Mean confidence</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {result.mean_confidence != null ? `${(result.mean_confidence * 100).toFixed(1)}%` : "—"}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">Brier score</div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {result.brier_score != null ? result.brier_score.toFixed(3) : "—"}
                </div>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">{result.note}</p>
          </SectionCard>

          <SectionCard title="Performance by regime" subtitle="Measured accuracy per market regime">
            <div className="space-y-2">
              {result.by_regime.map((r) => (
                <div key={r.regime} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
                  <span className="font-medium text-slate-300">{REGIME_LABELS[r.regime] ?? r.regime}</span>
                  <span className="tabular-nums text-slate-500">n={r.n}</span>
                  <span className="font-semibold tabular-nums text-slate-200">
                    {(r.accuracy * 100).toFixed(1)}%
                  </span>
                  <span className="tabular-nums text-slate-500">
                    {r.mean_error_pct > 0 ? "+" : ""}{r.mean_error_pct.toFixed(2)}pp
                  </span>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Failure categories" subtitle="Ranked by frequency in this backtest">
            {result.failure_categories.length === 0 ? (
              <p className="text-sm text-slate-500">No failures in this window.</p>
            ) : (
              <div className="space-y-2">
                {result.failure_categories.map((f) => (
                  <div key={f.failure_mode} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs">
                    <span className="font-medium text-rose-300">
                      {f.failure_mode.replace(/_/g, " ")}
                    </span>
                    <span className="tabular-nums text-slate-500">{f.count}×</span>
                    <span className="tabular-nums text-slate-500">
                      {(f.share * 100).toFixed(0)}%
                    </span>
                    <span className="tabular-nums text-slate-500">
                      {f.mean_error_pct > 0 ? "+" : ""}{f.mean_error_pct.toFixed(2)}pp
                    </span>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          <SectionCard title="Resolved predictions" subtitle="Most recent first">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-xs">
                <thead>
                  <tr className="border-b border-slate-700/60 text-left text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="px-2 py-1">Day</th>
                    <th className="px-2 py-1">Dir</th>
                    <th className="px-2 py-1 text-right">Conf</th>
                    <th className="px-2 py-1 text-right">Expected</th>
                    <th className="px-2 py-1 text-right">Actual</th>
                    <th className="px-2 py-1 text-right">Error</th>
                    <th className="px-2 py-1">Regime</th>
                    <th className="px-2 py-1 text-right">Correct</th>
                  </tr>
                </thead>
                <tbody>
                  {result.predictions.slice(0, 50).map((p) => (
                    <tr key={p.day_index} className="border-b border-slate-800/40">
                      <td className="px-2 py-1 tabular-nums text-slate-400">{p.day_index}</td>
                      <td className="px-2 py-1">
                        <span className={p.direction === "LONG" ? "text-emerald-400" : "text-rose-400"}>
                          {p.direction}
                        </span>
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-300">
                        {(p.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-emerald-300">
                        {fmtPct(p.expected_move_pct)}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-rose-300">
                        {fmtPct(p.actual_move_pct)}
                      </td>
                      <td className="px-2 py-1 text-right tabular-nums text-slate-400">
                        {p.error_pct > 0 ? "+" : ""}{p.error_pct.toFixed(2)}pp
                      </td>
                      <td className="px-2 py-1 text-slate-500">
                        {REGIME_LABELS[p.regime] ?? p.regime}
                      </td>
                      <td className="px-2 py-1 text-right">
                        <span className={p.correct ? "text-emerald-400" : "text-rose-400"}>
                          {p.correct ? "✓" : "✗"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
