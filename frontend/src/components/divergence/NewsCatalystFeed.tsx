"use client";
import { useState } from "react";

/**
 * Live Market Catalyst — news feed with AI sentiment tags and faction colors.
 *
 * Faction badge colors:
 *   institutional → deep blue/silver
 *   retail        → vibrant orange/neon
 * Sentiment tag colors:
 *   Bullish → emerald, Bearish → rose, Neutral → slate
 */
export type NewsItem = {
  title: string;
  url: string;
  source: string;
  published_at: string;
  tickers: string[];
  sentiment_score: number;
  sentiment_tag: "Bullish" | "Bearish" | "Neutral";
  faction: "retail" | "institutional";
  data_mode: string;
};

const SENTIMENT_STYLES: Record<string, string> = {
  Bullish: "bg-emerald-500/15 text-emerald-300",
  Bearish: "bg-rose-500/15 text-rose-300",
  Neutral: "bg-slate-500/15 text-slate-300",
};

const FACTION_STYLES: Record<string, { badge: string; label: string }> = {
  institutional: { badge: "bg-blue-500/15 text-blue-300 border-blue-500/30", label: "SMART MONEY" },
  retail: { badge: "bg-orange-500/15 text-orange-300 border-orange-500/30", label: "APE MONEY" },
};

export default function NewsCatalystFeed({
  items,
  loading,
}: {
  items: NewsItem[];
  loading?: boolean;
}) {
  const [filter, setFilter] = useState<"all" | "retail" | "institutional">("all");
  const shown = filter === "all" ? items : items.filter((i) => i.faction === filter);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex gap-1">
          {(["all", "institutional", "retail"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1 text-[10px] font-semibold transition-colors ${
                filter === f
                  ? f === "retail"
                    ? "bg-orange-500 text-black"
                    : f === "institutional"
                      ? "bg-blue-500 text-white"
                      : "bg-slate-600 text-white"
                  : "bg-white/5 text-slate-400 hover:bg-white/10"
              }`}
            >
              {f === "all" ? "All" : f === "institutional" ? "Smart Money" : "Ape Money"}
            </button>
          ))}
        </div>
        <span className="text-[10px] text-slate-500">{shown.length} headlines</span>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {loading ? (
          <div className="space-y-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl bg-white/5" />
            ))}
          </div>
        ) : shown.length === 0 ? (
          <p className="py-8 text-center text-xs text-slate-500">
            No headlines for this faction yet.
          </p>
        ) : (
          shown.map((item, i) => {
            const faction = FACTION_STYLES[item.faction] ?? FACTION_STYLES.institutional;
            return (
              <article
                key={i}
                className="rounded-xl border border-slate-700/50 bg-white/[0.02] p-3 transition-colors hover:bg-white/[0.05]"
              >
                <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
                  <span className={`rounded-full border px-2 py-0.5 text-[9px] font-bold tracking-wide ${faction.badge}`}>
                    {faction.label}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-[9px] font-bold ${SENTIMENT_STYLES[item.sentiment_tag]}`}>
                    {item.sentiment_tag}
                  </span>
                  {item.tickers.map((t) => (
                    <span key={t} className="rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold text-slate-300">
                      {t}
                    </span>
                  ))}
                </div>
                <h4 className="text-xs font-medium leading-relaxed text-slate-200">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-blue-300"
                    >
                      {item.title}
                    </a>
                  ) : (
                    item.title
                  )}
                </h4>
                <div className="mt-1 flex items-center justify-between text-[9px] text-slate-500">
                  <span>{item.source}</span>
                  <span className="tabular-nums">
                    score {item.sentiment_score > 0 ? "+" : ""}{item.sentiment_score.toFixed(2)}
                  </span>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
}
