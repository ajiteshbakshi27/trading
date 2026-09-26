"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import AutopsyReport from "@/components/research/AutopsyReport";
import { api } from "@/lib/api";
import { INSUFFICIENT_DATA, fmtPct } from "@/lib/research";

type Prediction = {
  prediction_id: string;
  thesis_id: string;
  symbol: string;
  direction: string;
  confidence: number;
  entry_price: number;
  expected_move_pct: number;
  horizon: string;
  status: string;
  regime: string;
  data_mode: string;
};

type Outcome = {
  actual_move_pct: number;
  expected_move_pct: number;
  error_pct: number;
  correct: boolean;
  realized_vol: number | null;
  resolution_source: string;
};

export default function ModelAutopsyPage() {
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [autopsy, setAutopsy] = useState<any>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api<any>("/api/predictions?limit=100");
      setPredictions(res.predictions ?? []);
      setError("");
    } catch (e: any) {
      setError(e.message || "Failed to load predictions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = predictions.find((p) => p.prediction_id === activeId) ?? predictions[0] ?? null;

  useEffect(() => {
    if (!active) {
      setOutcome(null);
      setAutopsy(null);
      return;
    }
    api<any>(`/api/predictions/${active.prediction_id}`)
      .then((res) => {
        setOutcome(res.outcome);
        setAutopsy(res.autopsy);
      })
      .catch(() => {
        setOutcome(null);
        setAutopsy(null);
      });
  }, [active]);

  useEffect(() => {
    api<any>("/api/model/failure-analysis")
      .then(setAnalysis)
      .catch(() => setAnalysis(null));
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-white/5" />
        <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
      </div>
    );
  }

  const resolved = analysis?.analysis?.resolved_predictions ?? 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Research</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Model Autopsy</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            When a prediction resolves incorrectly, we investigate why — using the
            evidence frozen at issue time.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="rounded-full bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
          >
            Refresh
          </button>
          <DataModeBadge mode={active?.data_mode ?? "mock"} />
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : !active ? (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
          <p className="text-sm text-slate-400">
            No predictions exist yet. Predictions are created from theses in the
            Thesis Lab.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {predictions.map((p) => (
              <button
                key={p.prediction_id}
                onClick={() => setActiveId(p.prediction_id)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  p.prediction_id === active.prediction_id
                    ? "bg-emerald-500 text-black"
                    : "bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                {p.symbol} · {p.direction} · {p.status}
              </button>
            ))}
          </div>

          <SectionCard
            title={`${active.symbol} — prediction`}
            subtitle={`${active.direction} · confidence ${(active.confidence * 100).toFixed(1)}% · horizon ${active.horizon}`}
            badge={
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                  active.status === "resolved"
                    ? "bg-slate-500/15 text-slate-300"
                    : "bg-emerald-500/15 text-emerald-300"
                }`}
              >
                {active.status.toUpperCase()}
              </span>
            }
          >
            {outcome ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Expected
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-emerald-300">
                    {fmtPct(outcome.expected_move_pct)}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Actual
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
                    {fmtPct(outcome.actual_move_pct)}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Error
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
                    {outcome.error_pct > 0 ? "+" : ""}
                    {outcome.error_pct.toFixed(2)}pp
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Correct
                  </div>
                  <div
                    className={`mt-1 text-lg font-bold ${
                      outcome.correct ? "text-emerald-300" : "text-rose-300"
                    }`}
                  >
                    {outcome.correct ? "Yes" : "No"}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-sm text-slate-500">
                This prediction has not been resolved yet.
              </p>
            )}
          </SectionCard>

          <SectionCard
            title="Autopsy"
            subtitle="Per-feature verdicts and the ranked failure mode."
          >
            <AutopsyReport autopsy={autopsy} />
          </SectionCard>

          <SectionCard
            title="Aggregate failure analysis"
            subtitle="Withheld until the sample floor is met."
            badge={
              analysis?.status === "insufficient_data" ? (
                <span className="rounded-full bg-rose-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-rose-300 ring-1 ring-rose-500/30">
                  {INSUFFICIENT_DATA}
                </span>
              ) : (
                <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
                  {resolved} resolved
                </span>
              )
            }
          >
            {analysis?.status === "insufficient_data" ? (
              <p className="text-sm text-slate-500">
                {analysis.insufficiency?.note ??
                  "Statistics are withheld until enough resolved predictions exist."}
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Accuracy
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                    {analysis?.analysis?.accuracy != null
                      ? `${(analysis.analysis.accuracy * 100).toFixed(1)}%`
                      : "—"}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Mean error
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                    {analysis?.analysis?.mean_error_pct != null
                      ? `${analysis.analysis.mean_error_pct.toFixed(2)}pp`
                      : "—"}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Mean confidence
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                    {analysis?.analysis?.mean_confidence != null
                      ? `${(analysis.analysis.mean_confidence * 100).toFixed(1)}%`
                      : "—"}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500">
                    Brier score
                  </div>
                  <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                    {analysis?.analysis?.brier_score != null
                      ? analysis.analysis.brier_score.toFixed(3)
                      : "—"}
                  </div>
                </div>
              </div>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}
