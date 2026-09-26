"use client";
import { LAYER_META } from "@/lib/research";
import { ACCENT_BG, ACCENT_RING, ACCENT_TEXT } from "./EvidenceBar";

/**
 * Timestamped information-propagation chain: EVENT → NEWS → PREDICTION →
 * REDDIT → X → ORDER FLOW → PRICE. Clicking a node selects it and shows the
 * detail panel. Ordering is a timestamp fact; causation is never asserted.
 */
export type FlowStep = {
  step_id: string;
  layer: string;
  timestamp: string;
  lag_s: number;
  signal: string;
  magnitude: number;
  z_score?: number;
  confidence: number;
  freshness: string;
  freshness_s?: number;
  data_mode: string;
  relation?: string;
  source_label: string;
  contribution?: number;
  raw?: Record<string, unknown>;
};

export default function FlowGraph({
  steps,
  selected,
  onSelect,
  symbol,
}: {
  steps: FlowStep[];
  selected: string | null;
  onSelect: (layer: string | null) => void;
  symbol: string;
}) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex min-w-[720px] items-stretch gap-0">
        {steps.map((step, i) => {
          const meta = LAYER_META[step.layer] ?? {
            label: step.layer,
            accent: "uncertainty",
          };
          const isSelected = selected === step.layer;
          return (
            <div key={step.step_id} className="flex flex-1 items-center">
              <button
                type="button"
                onClick={() => onSelect(isSelected ? null : step.layer)}
                aria-pressed={isSelected}
                className={`group flex min-h-[96px] w-full flex-col items-center justify-center gap-1 rounded-xl border px-3 py-3 text-center transition-all duration-200 ${ACCENT_RING[meta.accent]} ${
                  isSelected
                    ? "bg-white/10 ring-2 ring-white/30"
                    : "bg-white/[0.03] hover:bg-white/[0.07]"
                }`}
              >
                <span className={`text-[10px] font-semibold uppercase tracking-wider ${ACCENT_TEXT[meta.accent]}`}>
                  {meta.label}
                </span>
                <span className="text-sm font-bold tabular-nums text-slate-100">
                  {step.signal}
                </span>
                <span className="text-[10px] tabular-nums text-slate-500">
                  {step.lag_s}s
                </span>
                <span className={`mt-0.5 inline-flex h-1 w-10 overflow-hidden rounded-full bg-white/5`}>
                  <span
                    className={`h-full ${ACCENT_BG[meta.accent]}`}
                    style={{
                      width: `${Math.min(100, Math.abs(step.contribution ?? 0) * 100)}%`,
                    }}
                  />
                </span>
              </button>
              {i < steps.length - 1 && (
                <div className="mx-1 flex shrink-0 flex-col items-center gap-0.5" aria-hidden>
                  <span className="text-[10px] tabular-nums text-slate-600">
                    +{steps[i + 1].lag_s - step.lag_s}s
                  </span>
                  <span className="text-slate-600">→</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="mt-2 text-[10px] text-slate-600">
        {symbol} · information-propagation chain. Timestamps show ordering;
        no causal relationship is asserted.
      </p>
    </div>
  );
}
