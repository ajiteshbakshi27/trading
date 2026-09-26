"use client";
import DataModeBadge from "./DataModeBadge";
import { FAILURE_LABELS, VERDICT_STYLES, fmtPct } from "@/lib/research";

/**
 * Prediction Failure Autopsy. Shows the issued prediction, the realized
 * outcome, per-feature verdicts and the ranked failure mode — with cautious
 * language throughout.
 */
export default function AutopsyReport({
  autopsy,
}: {
  autopsy: {
    autopsy_id: string;
    prediction_id: string;
    symbol: string;
    direction: string;
    confidence: number;
    expected_move_pct: number;
    actual_move_pct: number;
    error_pct: number;
    issued_regime: string;
    realized_regime: string | null;
    regime_mismatch: boolean;
    failure_mode: string;
    mode_likelihood: number;
    verdicts: Array<{
      feature: string;
      label: string;
      verdict: string;
      wording: string;
      issued_z_score: number;
      observed_z_score: number | null;
      contribution_share: number;
      evidence: string[];
    }>;
    evidence_notes: string[];
    data_mode: string;
    methodology: string;
    disclaimer: string;
  } | null;
}) {
  if (!autopsy) {
    return (
      <p className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">
        No autopsy exists. Autopsies are only produced when a prediction
        resolves incorrectly.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Direction
          </div>
          <div className="mt-1 text-lg font-bold text-slate-100">
            {autopsy.direction}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Confidence
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
            {(autopsy.confidence * 100).toFixed(1)}%
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Expected
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-emerald-300">
            {fmtPct(autopsy.expected_move_pct)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Actual
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
            {fmtPct(autopsy.actual_move_pct)}
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-rose-500/20 bg-rose-500/5 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-rose-300">
              Likely failure mode
            </div>
            <div className="mt-1 text-sm font-semibold text-slate-100">
              {FAILURE_LABELS[autopsy.failure_mode] ?? autopsy.failure_mode}
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              Likelihood
            </div>
            <div className="text-sm font-bold tabular-nums text-rose-300">
              {(autopsy.mode_likelihood * 100).toFixed(0)}%
            </div>
          </div>
        </div>
        {autopsy.regime_mismatch ? (
          <p className="mt-2 text-xs text-amber-300">
            Regime mismatch: issued {autopsy.issued_regime}, realized{" "}
            {autopsy.realized_regime ?? "unknown"}.
          </p>
        ) : null}
      </div>

      <div>
        <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Signal autopsy
        </h4>
        <ul className="space-y-2">
          {autopsy.verdicts.map((v) => (
            <li
              key={v.feature}
              className="rounded-xl border border-slate-700/50 bg-white/[0.02] p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold text-slate-200">
                  {v.label}
                </span>
                <span
                  className={`text-[10px] font-semibold uppercase tracking-wider ${VERDICT_STYLES[v.verdict]}`}
                >
                  {v.verdict}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-400">{v.wording}</p>
              <div className="mt-1 flex flex-wrap gap-3 text-[10px] tabular-nums text-slate-500">
                <span>
                  issued z={v.issued_z_score > 0 ? "+" : ""}
                  {v.issued_z_score.toFixed(2)}
                </span>
                <span>
                  observed z=
                  {v.observed_z_score === null
                    ? "—"
                    : `${v.observed_z_score > 0 ? "+" : ""}${v.observed_z_score.toFixed(2)}`}
                </span>
                <span>share {(v.contribution_share * 100).toFixed(1)}%</span>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {autopsy.evidence_notes.length > 0 ? (
        <div className="rounded-lg border border-slate-700/50 bg-black/20 p-3">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Evidence
          </h4>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-400">
            {autopsy.evidence_notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="text-[10px] text-slate-600">{autopsy.disclaimer}</p>
      <div className="flex items-center justify-between">
        <DataModeBadge mode={autopsy.data_mode} />
      </div>
    </div>
  );
}
