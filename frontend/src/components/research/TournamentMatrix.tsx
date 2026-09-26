"use client";
import DataModeBadge from "./DataModeBadge";
import { INSUFFICIENT_DATA, REGIME_LABELS, fmtConf } from "@/lib/research";

/**
 * Adaptive Signal Tournament matrix. Rows are ablation arms, columns are
 * regimes. Cells show measured directional accuracy, or INSUFFICIENT DATA
 * when the sample is too small. No "winner" labels are produced.
 */
export default function TournamentMatrix({
  matrix,
}: {
  matrix: {
    baseline_experiment_id: string;
    columns: string[];
    rows: Array<{
      regime: string;
      n: number;
      metrics: {
        n: number;
        n_decisions: number;
        directional_accuracy: number | null;
        mean_abs_error_pct: number | null;
        brier_score: number | null;
        withheld: string[];
      };
      delta_vs_full: Record<string, number | null>;
      status: string;
      label: string;
    }>;
    metric: string;
    status: string;
    label: string;
    sample_size: number;
    required_sample_size: number;
    note: string;
    data_mode: string;
    caveat: string;
  } | null;
}) {
  if (!matrix || matrix.status === "insufficient_data") {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 p-6 text-center">
        <p className="text-sm font-semibold text-rose-300">{INSUFFICIENT_DATA}</p>
        <p className="mt-1 text-xs text-slate-500">
          {matrix?.note ??
            "The tournament needs more resolved observations before any cell can report a number."}
        </p>
        {matrix ? (
          <p className="mt-1 text-[10px] tabular-nums text-slate-600">
            sample {matrix.sample_size} / required {matrix.required_sample_size}
          </p>
        ) : null}
      </div>
    );
  }

  // Group rows by arm (experiment). Each arm contributes one row per regime.
  const arms = new Map<string, typeof matrix.rows>();
  for (const row of matrix.rows) {
    const key = row.regime; // placeholder; real grouping by arm comes from results
    if (!arms.has(key)) arms.set(key, []);
    arms.get(key)!.push(row);
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-xs">
          <thead>
            <tr>
              <th className="border-b border-slate-700/60 px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Arm
              </th>
              {matrix.columns.map((col) => (
                <th
                  key={col}
                  className="border-b border-slate-700/60 px-3 py-2 text-right text-[10px] font-semibold uppercase tracking-wider text-slate-500"
                >
                  {REGIME_LABELS[col] ?? col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row, i) => (
              <tr key={`${row.regime}-${i}`} className="border-b border-slate-800/40">
                <td className="px-3 py-2 text-slate-300">
                  {REGIME_LABELS[row.regime] ?? row.regime}
                  <span className="ml-1 text-[10px] text-slate-600">
                    n={row.n}
                  </span>
                </td>
                {matrix.columns.map((col) => {
                  const cell = row.regime === col ? row : null;
                  return (
                    <td
                      key={col}
                      className="px-3 py-2 text-right tabular-nums"
                    >
                      {cell ? (
                        cell.status === "insufficient_data" ? (
                          <span className="text-[10px] font-semibold text-rose-300">
                            {INSUFFICIENT_DATA}
                          </span>
                        ) : (
                          <span className="font-semibold text-slate-200">
                            {cell.metrics.directional_accuracy !== null
                              ? `${(cell.metrics.directional_accuracy * 100).toFixed(0)}%`
                              : "—"}
                          </span>
                        )
                      ) : (
                        <span className="text-slate-700">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500">{matrix.note}</p>
      <p className="text-[10px] text-slate-600">{matrix.caveat}</p>
      <div className="flex items-center justify-between">
        <DataModeBadge mode={matrix.data_mode} note={`n=${matrix.sample_size}`} />
      </div>
    </div>
  );
}
