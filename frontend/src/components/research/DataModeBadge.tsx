"use client";
import { INSUFFICIENT_DATA } from "@/lib/research";

/**
 * Provenance badge. One component for every data-mode label in the product,
 * so LIVE / SIMULATED / MOCK / BACKTEST / INSUFFICIENT DATA always render the
 * same way and always mean the same thing.
 */
const STYLES: Record<string, string> = {
  live: "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30",
  simulated: "bg-amber-500/15 text-amber-300 ring-amber-500/30",
  mock: "bg-slate-500/15 text-slate-300 ring-slate-500/30",
  backtest: "bg-cyan-500/15 text-cyan-300 ring-cyan-500/30",
  insufficient_data: "bg-rose-500/15 text-rose-300 ring-rose-500/30",
};

const LABELS: Record<string, string> = {
  live: "LIVE",
  simulated: "SIMULATED SCENARIO",
  mock: "MOCK",
  backtest: "BACKTEST",
  insufficient_data: INSUFFICIENT_DATA,
};

export default function DataModeBadge({ mode, note }: { mode: string; note?: string }) {
  const cls = STYLES[mode] ?? STYLES.mock;
  const label = LABELS[mode] ?? mode.toUpperCase();
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-semibold tracking-wide ring-1 ${cls}`}>
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-current" />
      {label}
      {note ? <span className="font-normal opacity-70">· {note}</span> : null}
    </span>
  );
}
