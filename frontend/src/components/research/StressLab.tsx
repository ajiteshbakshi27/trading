"use client";
import DataModeBadge from "./DataModeBadge";
import { fmtConf } from "@/lib/research";

/**
 * Thesis Stress Lab. Shows the baseline confidence and each perturbation
 * scenario with its explicit rule, the recomputed confidence, and whether
 * the thesis direction survived.
 */
export type ScenarioResult = {
  scenario: string;
  label: string;
  rule: string;
  perturbed_confidence: number;
  delta_confidence: number;
  flipped: boolean;
  survives: boolean;
  perturbed_evidence: Array<{ feature: string; layer: string; z_before: number }>;
  components: Record<string, number>;
};

export default function StressLab({
  stress,
}: {
  stress: {
    stress_id: string;
    thesis_id: string;
    symbol: string;
    direction: string;
    baseline_confidence: number;
    mean_perturbed_confidence: number;
    worst_case_confidence: number;
    robustness: number;
    fragility: number;
    robustness_label: string;
    scenarios: ScenarioResult[];
    neutral_floor: number;
    data_mode: string;
    methodology: string;
    notes: string[];
  } | null;
}) {
  if (!stress) {
    return (
      <p className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">
        No stress test has been run on this thesis yet.
      </p>
    );
  }
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Baseline
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
            {fmtConf(stress.baseline_confidence)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Mean perturbed
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
            {fmtConf(stress.mean_perturbed_confidence)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Worst case
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
            {fmtConf(stress.worst_case_confidence)}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
          <div className="text-[10px] uppercase tracking-wider text-slate-500">
            Robustness
          </div>
          <div className="mt-1 text-lg font-bold tabular-nums text-emerald-300">
            {(stress.robustness * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <p className="rounded-lg border border-slate-700/50 bg-black/20 p-3 text-xs text-slate-400">
        {stress.methodology}
      </p>

      <ul className="space-y-2">
        {stress.scenarios.map((sc) => (
          <li
            key={sc.scenario}
            className={`rounded-xl border p-3 ${
              sc.flipped
                ? "border-rose-500/30 bg-rose-500/5"
                : sc.survives
                  ? "border-slate-700/50 bg-white/[0.02]"
                  : "border-amber-500/20 bg-amber-500/5"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs font-semibold text-slate-200">
                {sc.label}
              </span>
              <span
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  sc.flipped
                    ? "bg-rose-500/15 text-rose-300"
                    : sc.survives
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-amber-500/15 text-amber-300"
                }`}
              >
                {sc.flipped
                  ? "DIRECTION FLIPPED"
                  : sc.survives
                    ? "SURVIVES"
                    : "WEAKENED"}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-xs">
              <span className="text-slate-500">
                confidence{" "}
                <span className="font-semibold tabular-nums text-slate-200">
                  {fmtConf(sc.perturbed_confidence)}
                </span>
              </span>
              <span className="text-slate-500">
                Δ{" "}
                <span
                  className={`font-semibold tabular-nums ${
                    sc.delta_confidence < 0 ? "text-rose-300" : "text-emerald-300"
                  }`}
                >
                  {sc.delta_confidence > 0 ? "+" : ""}
                  {(sc.delta_confidence * 100).toFixed(1)}pp
                </span>
              </span>
            </div>
            <code className="mt-2 block rounded bg-black/30 px-2 py-1 text-[10px] text-slate-400">
              {sc.rule}
            </code>
          </li>
        ))}
      </ul>

      {stress.notes.length > 0 ? (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
            Notes
          </h4>
          <ul className="list-inside list-disc space-y-0.5 text-xs text-amber-200/80">
            {stress.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">{stress.robustness_label}</p>
        <DataModeBadge mode={stress.data_mode} />
      </div>
    </div>
  );
}
