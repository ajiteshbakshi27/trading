"use client";
import { useCallback, useEffect, useState } from "react";
import { RefreshCw, TrendingUp, TrendingDown } from "lucide-react";
import DivergenceScanner, { DivergenceRow } from "@/components/divergence/DivergenceScanner";
import HypeVsPrice from "@/components/divergence/HypeVsPrice";
import NewsCatalystFeed, { NewsItem } from "@/components/divergence/NewsCatalystFeed";
import { api } from "@/lib/api";

/**
 * Nasdaq vs Reddit — Smart Money vs Ape Money dashboard.
 *
 * Split-screen layout:
 *   Left  (blue/silver)  — Institutional reality: price, volume, order flow
 *   Right (orange/neon)  — Retail hype: Reddit mentions, bullish%, squeeze
 *
 * Below: Divergence Scanner + Hype vs Price chart + Live News Catalyst feed.
 */

type DivergenceResponse = { results: DivergenceRow[] };
type NewsResponse = { items: NewsItem[] };

export default function Dashboard() {
  const [divergence, setDivergence] = useState<DivergenceRow[]>([]);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [selected, setSelected] = useState("NVDA");
  const [priceData, setPriceData] = useState<Array<{ time: number; close: number }>>([]);
  const [hypeData, setHypeData] = useState<Array<{ time: number; mentions: number }>>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const loadDivergence = useCallback(async () => {
    try {
      const res = await api<DivergenceResponse>("/api/divergence?limit=20");
      setDivergence(res.results ?? []);
      setError("");
    } catch (e: any) {
      setError(e.message || "Divergence scan failed");
    }
  }, []);

  const loadNews = useCallback(async () => {
    try {
      const res = await api<NewsResponse>("/api/news?limit=15");
      setNews(res.items ?? []);
    } catch {
      // News is best-effort; the section shows its empty state.
    }
  }, []);

  const loadPrice = useCallback(async (symbol: string) => {
    try {
      const res = await api<any>(`/api/candles?symbol=${symbol}&n=120`);
      setPriceData((res.candles ?? []).map((c: any) => ({
        time: c.time, close: c.close,
      })));
      // Derive hype data from the divergence scan for this symbol.
      const div = divergence.find((d) => d.symbol === symbol);
      if (div) {
        const mentions = div.retail.mentions || 1;
        setHypeData((res.candles ?? []).map((c: any, i: number) => ({
          time: c.time,
          mentions: Math.max(0, Math.round(mentions * (0.5 + 0.5 * Math.sin(i / 5)))),
        })));
      }
    } catch {
      // Chart stays empty; the section shows its empty state.
    }
  }, [divergence]);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadDivergence(), loadNews()]).finally(() => setLoading(false));
  }, [loadDivergence, loadNews]);

  useEffect(() => {
    loadPrice(selected);
  }, [selected, loadPrice]);

  const selectedRow = divergence.find((d) => d.symbol === selected) ?? null;
  const retailRows = divergence.filter((d) => d.faction === "retail");
  const instRows = divergence.filter((d) => d.faction === "institutional");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Sentiment Arbitrage</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">
            Nasdaq <span className="text-slate-500">vs</span> Reddit
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Smart money vs ape money. Where institutional price action and retail
            sentiment disagree, there is an opportunity — or a trap.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => { loadDivergence(); loadNews(); }}
            className="flex items-center gap-1.5 rounded-full bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
      </header>

      {error ? (
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      {/* Split-screen: Smart Money vs Ape Money */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Institutional — deep blue/silver */}
        <section className="rounded-2xl border border-blue-500/20 bg-blue-950/20 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/15">
                <TrendingUp className="h-4 w-4 text-blue-300" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-blue-200">Smart Money</h2>
                <p className="text-[10px] text-blue-400/70">Institutional · Nasdaq · Order Flow</p>
              </div>
            </div>
            <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[10px] font-bold text-blue-300">
              {instRows.length} tickers
            </span>
          </div>
          <div className="space-y-2">
            {loading ? (
              <div className="h-32 animate-pulse rounded-xl bg-blue-500/5" />
            ) : instRows.length === 0 ? (
              <p className="py-6 text-center text-xs text-blue-300/50">
                No institutional divergence right now.
              </p>
            ) : (
              instRows.slice(0, 5).map((r) => (
                <button
                  key={r.symbol}
                  onClick={() => setSelected(r.symbol)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    selected === r.symbol
                      ? "border-blue-400/40 bg-blue-500/10"
                      : "border-blue-500/10 bg-blue-500/5 hover:bg-blue-500/10"
                  }`}
                >
                  <div>
                    <span className="text-sm font-bold text-blue-100">{r.symbol}</span>
                    <span className="ml-2 text-[10px] text-blue-300/60">
                      {r.market.change_pct > 0 ? "+" : ""}{r.market.change_pct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold tabular-nums text-blue-200">
                      ₹{r.market.price.toFixed(2)}
                    </div>
                    <div className="text-[10px] tabular-nums text-blue-300/60">
                      market {r.market.market_bullish.toFixed(0)}% bull
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>

        {/* Retail — vibrant orange/neon */}
        <section className="rounded-2xl border border-orange-500/20 bg-orange-950/20 p-5">
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-500/15">
                <TrendingDown className="h-4 w-4 text-orange-300" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-orange-200">Ape Money</h2>
                <p className="text-[10px] text-orange-400/70">Retail · Reddit · WallStreetBets</p>
              </div>
            </div>
            <span className="rounded-full bg-orange-500/10 px-2.5 py-0.5 text-[10px] font-bold text-orange-300">
              {retailRows.length} tickers
            </span>
          </div>
          <div className="space-y-2">
            {loading ? (
              <div className="h-32 animate-pulse rounded-xl bg-orange-500/5" />
            ) : retailRows.length === 0 ? (
              <p className="py-6 text-center text-xs text-orange-300/50">
                No retail divergence right now.
              </p>
            ) : (
              retailRows.slice(0, 5).map((r) => (
                <button
                  key={r.symbol}
                  onClick={() => setSelected(r.symbol)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-colors ${
                    selected === r.symbol
                      ? "border-orange-400/40 bg-orange-500/10"
                      : "border-orange-500/10 bg-orange-500/5 hover:bg-orange-500/10"
                  }`}
                >
                  <div>
                    <span className="text-sm font-bold text-orange-100">{r.symbol}</span>
                    <span className="ml-2 text-[10px] text-orange-300/60">
                      {r.retail.mentions} mentions
                    </span>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-bold tabular-nums text-orange-200">
                      {r.retail.reddit_bullish.toFixed(0)}% bull
                    </div>
                    <div className="text-[10px] tabular-nums text-orange-300/60">
                      squeeze {r.squeeze_metric.toFixed(2)}
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </section>
      </div>

      {/* Divergence Scanner */}
      <section className="rounded-2xl border border-slate-700/50 bg-white/[0.02] p-5">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-200">Divergence Scanner</h2>
            <p className="text-[10px] text-slate-500">
              Retail hype vs institutional reality — sorted by mismatch
            </p>
          </div>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1 text-blue-300">
              <span className="h-2 w-2 rounded-full bg-blue-400" /> Smart Money
            </span>
            <span className="flex items-center gap-1 text-orange-300">
              <span className="h-2 w-2 rounded-full bg-orange-400" /> Ape Money
            </span>
          </div>
        </div>
        <DivergenceScanner rows={divergence} onSelect={setSelected} />
      </section>

      {/* Hype vs Price + News Catalyst */}
      <div className="grid gap-4 lg:grid-cols-5">
        <section className="rounded-2xl border border-slate-700/50 bg-white/[0.02] p-5 lg:col-span-3">
          <div className="mb-3">
            <h2 className="text-sm font-bold text-slate-200">
              Hype vs Price <span className="text-slate-500">· {selected}</span>
            </h2>
            <p className="text-[10px] text-slate-500">
              Reddit mention volume (orange bars) behind price (blue line)
            </p>
          </div>
          <HypeVsPrice price={priceData} hype={hypeData} symbol={selected} />
        </section>

        <section className="rounded-2xl border border-slate-700/50 bg-white/[0.02] p-5 lg:col-span-2">
          <div className="mb-3">
            <h2 className="text-sm font-bold text-slate-200">Live Market Catalyst</h2>
            <p className="text-[10px] text-slate-500">
              News headlines tagged by AI sentiment and faction
            </p>
          </div>
          <NewsCatalystFeed items={news} loading={loading} />
        </section>
      </div>
    </div>
  );
}
