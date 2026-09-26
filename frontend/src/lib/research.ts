/**
 * Shared constants and helpers for the research surfaces.
 *
 * The visual signature is defined once here and in globals.css so every
 * graph, card and timeline uses the same accent for the same layer.
 */

export const INSUFFICIENT_DATA = "INSUFFICIENT DATA";

export const LAYER_META: Record<string, { label: string; accent: string }> = {
  event: { label: "Event", accent: "information" },
  news: { label: "News", accent: "information" },
  prediction: { label: "Prediction Market", accent: "prediction" },
  reddit: { label: "Reddit", accent: "social" },
  x: { label: "X / Twitter", accent: "social" },
  order_flow: { label: "Order Flow", accent: "orderflow" },
  price: { label: "Price", accent: "price" },
};

export const FEATURE_META: Record<string, { label: string; accent: string }> = {
  order_flow: { label: "Order Flow", accent: "orderflow" },
  social: { label: "Social", accent: "social" },
  prediction: { label: "Prediction", accent: "prediction" },
  momentum: { label: "Momentum", accent: "price" },
  news: { label: "News", accent: "information" },
  quantum: { label: "Quantum", accent: "quantum" },
};

export const REGIME_LABELS: Record<string, string> = {
  trend: "Trend",
  high_vol: "High Volatility",
  mean_reversion: "Mean Reversion",
  range_bound: "Range Bound",
  unknown: "Unknown",
};

export const FAILURE_LABELS: Record<string, string> = {
  regime_misclassification: "Regime misclassification",
  volatility_underestimation: "Volatility underestimation",
  sentiment_deceit: "Social sentiment did not persist",
  flow_decay: "Order-flow signal decayed",
  prediction_divergence: "Prediction market diverged",
  liquidity_exhaustion: "Liquidity exhausted",
  conflicting_evidence: "Conflicting evidence at issue time",
  unclassified: "Unclassified",
};

export const VERDICT_STYLES: Record<string, string> = {
  supported: "text-emerald-400",
  contradicted: "text-rose-400",
  neutral: "text-slate-400",
  unavailable: "text-slate-500",
};

export function fmtPct(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export function fmtConf(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export function fmtNum(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

export function directionClass(dir: string): string {
  if (dir === "LONG") return "text-emerald-400";
  if (dir === "SHORT") return "text-rose-400";
  return "text-slate-400";
}

export function zClass(z: number): string {
  if (z > 0.15) return "text-emerald-400";
  if (z < -0.15) return "text-rose-400";
  return "text-slate-400";
}
