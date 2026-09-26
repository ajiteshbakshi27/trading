"use client";
import { useState } from "react";

/**
 * Divergence Scanner — Smart Money vs Ape Money table.
 * Sorted by divergence score. Faction colors:
 *   institutional = deep blue/silver, retail = vibrant orange/neon.
 */
export type DivergenceRow = {
  symbol: string;
  divergence_score: number;
  divergence_label: string;
  stance: string;
  squeeze_metric: number;
  squeeze_label: string;
  retail: { mentions: number; reddit_bullish: number; data_mode: string };
  market: { price: number; change_pct: number; market_bullish: number; data_mode: string };
  faction: string;
};

const STANCE_STYLES: Record<string, string> = {
  "RETAIL OVERHYPED": "bg-orange-500/15 text-orange-300",
  "SMART MONEY DIVERGENCE": "bg-blue-500/15 text-blue-300",
  "ALIGNED": "bg-slate-500/15 text-slate-300",
};

export default function DivergenceScanner({
  rows,
  onSelect,
}: {
  rows: DivergenceRow[];
  onSelect?: (symbol: string) => void;
}) {
  const [sortDesc, setSortDesc] = useState(true);
  const sorted = [...rows].sort((a, b) =>
    sortDesc ? b.divergence_score - a.divergence_score : a.divergence_score - b.divergence_score
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-xs">
        <thead>
          <tr className="border-b border-slate-700/60 text-left text-[10px] uppercase tracking-wider text-slate-500">
            <th className="px-3 py-2">Symbol</th>
            <th className="px-3 py-2 text-right">
              <button onClick={() => setSortDesc(!sortDesc)} className="hover:text-slate-300">
                Divergence {sortDesc ? "↓" : "↑"}
              </button>
            </th>
            <th className="px-3 py-2">Stance</th>
            <th className="px-3 py-2 text-right">Reddit Bullish</th>
            <th className="px-3 py-2 text-right">Market Bullish</th>
            <th className="px-3 py-2 text-right">Mentions</th>
            <th className="px-3 py-2 text-right">Squeeze</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr
              key={r.symbol}
              onClick={() => onSelect?.(r.symbol)}
              className="cursor-pointer border-b border-slate-800/40 transition-colors hover:bg-white/[0.04]"
            >
              <td className="px-3 py-2">
                <span className="font-semibold text-slate-100">{r.symbol}</span>
                <span className="ml-2 text-[10px] text-slate-500">
                  {r.faction === "retail" ? "🦍" : "🏛️"}
                </span>
              </td>
              <td className="px-3 py-2 text-right">
                <span className={`font-bold tabular-nums ${r.divergence_score > 50 ? "text-rose-300" : r.divergence_score > 25 ? "text-amber-300" : "text-slate-300"}`}>
                  {r.divergence_score.toFixed(0)}
                </span>
              </td>
              <td className="px-3 py-2">
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${STANCE_STYLES[r.stance] ?? STANCE_STYLES.ALIGNED}`}>
                  {r.stance}
                </span>
              </td>
              <td className="px-3 py-2 text-right">
                <span className="font-semibold tabular-nums text-orange-300">
                  {r.retail.reddit_bullish.toFixed(0)}%
                </span>
              </td>
              <td className="px-3 py-2 text-right">
                <span className={`font-semibold tabular-nums ${r.market.market_bullish >= 50 ? "text-blue-300" : "text-slate-400"}`}>
                  {r.market.market_bullish.toFixed(0)}%
                </span>
              </td>
              <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                {r.retail.mentions}
              </td>
              <td className="px-3 py-2 text-right">
                <span className={`tabular-nums ${r.squeeze_metric > 0.6 ? "text-rose-300" : r.squeeze_metric > 0.35 ? "text-amber-300" : "text-slate-400"}`}>
                  {r.squeeze_metric.toFixed(2)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
