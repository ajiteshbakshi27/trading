"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import TournamentMatrix from "@/components/research/TournamentMatrix";
import { api } from "@/lib/api";
import { INSUFFICIENT_DATA, REGIME_LABELS } from "@/lib/research";

type ExperimentResult = {
  experiment_id: string;
  name: string;
  features_disabled: string[];
  overall: {
    n: number;
    n_decisions: number;
    directional_accuracy: number | null;
    mean_abs_error_pct: number | null;
    brier_score: number | null;
    withheld: string[];
  };
  by_regime: Array<{
    regime: string;
    n: number;
    metrics: {
      directional_accuracy: number | null;
      mean_abs_error_pct: number | null;
    };
    delta_vs_full: Record<string, number | null>;
    status: string;
    label: string;
  }>;
  delta_vs_full: Record<string, number | null>;
  n_observations: number;
  data_mode: string;
  caveat: string;
};

export default function ResearchLabPage() {
  const [results, setResults] = useState<ExperimentResult[]>([]);
  const [matrix, setMatrix] = useState<any>(null);
  const [overview, setOverview] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [expRes, matrixRes, overviewRes] = await Promise.all([
        api<any>("/api/experiments?limit=50"),
        api<any>("/api/experiments/matrix?min_n=20"),
        api<any>("/api/research/overview"),
      ]);
      setResults(expRes.experiments ?? []);
      setMatrix(matrixRes.matrix ?? null);
      setOverview(overviewRes ?? null);
      setError("");
    } catch (e: any) {
      setError(e.message || "Failed to load research data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-white/5" />
        <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Research</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Research Lab</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Controlled ablations of the fusion model. Does each information
            source actually contribute?
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="rounded-full bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
          >
            Refresh
          </button>
          <DataModeBadge mode={matrix?.data_mode ?? "mock"} />
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : (
        <>
          {overview ? (
            <SectionCard
              title="Model evidence"
              subtitle="Raw record counts, not performance."
            >
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { label: "Predictions", value: overview.counts?.predictions ?? 0 },
                  { label: "Resolved", value: overview.counts?.resolved ?? 0 },
                  { label: "Experiments", value: overview.counts?.experiments ?? 0 },
                  { label: "Autopsies", value: overview.counts?.autopsies ?? 0 },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3"
                  >
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">
                      {item.label}
                    </div>
                    <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {(overview.model_versions ?? []).map((mv: any) => (
                  <span
                    key={mv.model_version}
                    className="rounded-full bg-cyan-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-cyan-300 ring-1 ring-cyan-500/20"
                  >
                    {mv.model_version}
                    {mv.active ? " · active" : ""}
                  </span>
                ))}
              </div>
            </SectionCard>
          ) : null}

          <SectionCard
            title="Signal tournament"
            subtitle="Arms differ only in which features are enabled."
            actions={
              <button
                onClick={() =>
                  api<any>("/api/experiments/matrix?min_n=20")
                    .then((res) => setMatrix(res.matrix))
                    .catch(() => {})
                }
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-black hover:bg-emerald-400"
              >
                Run tournament
              </button>
            }
          >
            <TournamentMatrix matrix={matrix} />
          </SectionCard>

          <SectionCard
            title="Arms"
            subtitle="Measured results per ablation."
          >
            {results.length === 0 ? (
              <p className="text-sm text-slate-500">
                No experiments have been run yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {results.map((r) => (
                  <li
                    key={r.experiment_id}
                    className="rounded-xl border border-slate-700/50 bg-white/[0.02] p-3"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-semibold text-slate-200">
                        {r.name}
                      </span>
                      <span className="text-[10px] tabular-nums text-slate-500">
                        n={r.overall?.n ?? 0} · decisions={r.overall?.n_decisions ?? 0}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-4 text-xs">
                      <span className="text-slate-500">
                        accuracy{" "}
                        <span className="font-semibold tabular-nums text-slate-200">
                          {r.overall?.directional_accuracy != null
                            ? `${(r.overall.directional_accuracy * 100).toFixed(1)}%`
                            : "—"}
                        </span>
                      </span>
                      <span className="text-slate-500">
                        MAE{" "}
                        <span className="font-semibold tabular-nums text-slate-200">
                          {r.overall?.mean_abs_error_pct != null
                            ? `${r.overall.mean_abs_error_pct.toFixed(2)}pp`
                            : "—"}
                        </span>
                      </span>
                      <span className="text-slate-500">
                        Brier{" "}
                        <span className="font-semibold tabular-nums text-slate-200">
                          {r.overall?.brier_score != null
                            ? r.overall.brier_score.toFixed(3)
                            : "—"}
                        </span>
                      </span>
                      {Array.isArray(r.features_disabled) && r.features_disabled.length > 0 ? (
                        <span className="text-slate-500">
                          disabled:{" "}
                          <span className="font-medium text-rose-300">
                            {r.features_disabled.join(", ")}
                          </span>
                        </span>
                      ) : (
                        <span className="text-emerald-300">full model</span>
                      )}
                    </div>
                    {r.overall?.withheld?.length > 0 ? (
                      <p className="mt-1 text-[10px] text-slate-600">
                        withheld: {r.overall.withheld.join(", ")}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}
