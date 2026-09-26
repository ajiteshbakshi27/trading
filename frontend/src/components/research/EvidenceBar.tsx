"use client";
import { FEATURE_META, fmtConf, zClass } from "@/lib/research";

/**
 * Static class map. Tailwind's JIT scans source for complete class strings,
 * so dynamic `text-${accent}` would silently produce nothing — these are
 * written out in full.
 */
const ACCENT_TEXT: Record<string, string> = {
  information: "text-information",
  social: "text-social",
  prediction: "text-prediction",
  orderflow: "text-orderflow",
  price: "text-price",
  risk: "text-risk",
  quantum: "text-quantum",
  uncertainty: "text-uncertainty",
};

const ACCENT_BG: Record<string, string> = {
  information: "bg-information",
  social: "bg-social",
  prediction: "bg-prediction",
  orderflow: "bg-orderflow",
  price: "bg-price",
  risk: "bg-risk",
  quantum: "bg-quantum",
  uncertainty: "bg-uncertainty",
};

const ACCENT_RING: Record<string, string> = {
  information: "border-information",
  social: "border-social",
  prediction: "border-prediction",
  orderflow: "border-orderflow",
  price: "border-price",
  risk: "border-risk",
  quantum: "border-quantum",
  uncertainty: "border-uncertainty",
};

/**
 * Horizontal contribution bars for each evidence feature. The bar length is
 * the feature's share of the fused confidence; the colour follows the visual
 * signature accent for that layer.
 */
export default function EvidenceBar({
  evidence,
}: {
  evidence: Array<{
    feature: string;
    z_score: number;
    contribution: number;
    confidence: number;
    data_mode?: string;
  }>;
}) {
  const sorted = [...evidence].sort(
    (a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)
  );
  return (
    <ul className="space-y-2">
      {sorted.map((ev) => {
        const meta = FEATURE_META[ev.feature] ?? {
          label: ev.feature,
          accent: "uncertainty",
        };
        const pct = Math.min(100, Math.abs(ev.contribution) * 100);
        return (
          <li key={ev.feature} className="flex items-center gap-3">
            <span className={`w-24 shrink-0 text-xs font-medium ${ACCENT_TEXT[meta.accent]}`}>
              {meta.label}
            </span>
            <div
              className="h-2 flex-1 overflow-hidden rounded-full bg-white/5"
              role="img"
              aria-label={`${meta.label} contribution ${(ev.contribution * 100).toFixed(1)}%`}
            >
              <div
                className={`h-full rounded-full ${ACCENT_BG[meta.accent]} transition-[width] duration-300`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={`w-14 text-right text-xs font-semibold tabular-nums ${zClass(ev.z_score)}`}>
              {ev.z_score > 0 ? "+" : ""}{ev.z_score.toFixed(2)}
            </span>
            <span className="w-12 text-right text-[10px] tabular-nums text-slate-500">
              {fmtConf(ev.confidence)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export { ACCENT_TEXT, ACCENT_BG, ACCENT_RING };
