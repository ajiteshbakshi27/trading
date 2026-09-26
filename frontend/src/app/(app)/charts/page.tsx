"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import SectionCard from "@/components/research/SectionCard";
import FlowGraph, { FlowStep } from "@/components/research/FlowGraph";

const SYMS = ["NVDA", "TSLA", "AAPL", "AMD", "MSFT", "GOOGL", "META", "INTC", "AMZN"];

export default function ChartsPage() {
  const [sym, setSym] = useState("NVDA");
  const [info, setInfo] = useState<any>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(true);
  const [auto, setAuto] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  const loadChart = useCallback(async () => {
    setLoading(true); setErr("");
    try {
      const r = await api<any>(`/api/candles?symbol=${sym}&n=150`);
      setInfo({ markers: (r.markers || []).length, source: r.source });
      const mod: any = await import("lightweight-charts");
      if (!ref.current) return;
      // Dispose the previous instance before re-creating (auto-refresh).
      try { chartRef.current?.remove(); } catch {}
      chartRef.current = null;
      ref.current.innerHTML = "";
      const chart = mod.createChart(ref.current, {
        layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "rgba(148,163,184,0.08)" }, horzLines: { color: "rgba(148,163,184,0.08)" } },
        width: ref.current.clientWidth, height: 420,
      });
      chartRef.current = chart;
      const series = chart.addSeries(mod.CandlestickSeries, {
        upColor: "#22C55E", downColor: "#EF4444",
        wickUpColor: "#22C55E", wickDownColor: "#EF4444", borderVisible: false,
      });
      series.setData(r.candles);
      const markers = (r.markers || []).map((m: any) => ({
        time: m.time, position: m.position, color: m.color,
        shape: m.shape, text: m.text,
      }));
      if (markers.length) {
        if (typeof series.setMarkers === "function") series.setMarkers(markers);
        else if (typeof mod.createSeriesMarkers === "function") mod.createSeriesMarkers(series, markers);
      }
      chart.timeScale().fitContent();
    } catch (e: any) {
      setErr(e.message || "Failed to load candles");
    } finally { setLoading(false); }
  }, [sym]);

  useEffect(() => {
    loadChart();
    return () => { try { chartRef.current?.remove(); } catch {} chartRef.current = null; };
  }, [loadChart]);

  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => loadChart(), 10000);
    return () => clearInterval(id);
  }, [auto, loadChart]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">Candlestick Charts + Agent Overlays</h1>
        {info?.source && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs ${
            info.source === "alphavantage" ? "bg-emerald-500/10 text-emerald-300" : "bg-white/5 text-slate-400"}`}>
            {info.source === "alphavantage" ? "● Live (Alpha Vantage)" : "Simulator"}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-400">
            <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)}
              className="accent-emerald-500" /> auto 10s
          </label>
          <button onClick={loadChart} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-300 ring-1 ring-white/10 hover:bg-white/10 disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {SYMS.map((s) => (
          <button key={s} onClick={() => setSym(s)}
            className={`rounded-lg px-3 py-1 text-sm ${s === sym ? "bg-emerald-500 text-black" : "glass"}`}>{s}</button>
        ))}
      </div>
      {err && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-300">{err}</p>}
      <div className="relative rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-xl">
        {loading && <div className="absolute inset-0 z-10 animate-pulse rounded-2xl bg-slate-900/60" />}
        <div ref={ref} className="w-full" />
        <div className="mt-2 text-xs text-slate-400">
          <span className="text-emerald-400">▲ Bet For / Buy</span> ·{" "}
          <span className="text-rose-400">▼ Bet Against</span>
          {info ? ` · ${info.markers} markers` : ""}
        </div>
      </div>
      <PropagationEmbed symbol={sym} />
    </div>
  );
}

function PropagationEmbed({ symbol }: { symbol: string }) {
  const [chain, setChain] = useState<any>(null);
  useEffect(() => {
    api<any>(`/api/research/cycle?symbol=${symbol}&persist=false`)
      .then((res) => setChain(res.chain ?? null))
      .catch(() => setChain(null));
  }, [symbol]);
  return (
    <div className="mt-4">
      <SectionCard
        title={`${symbol} — information flow`}
        subtitle="Compact propagation chain"
      >
        {chain?.propagation_steps?.length ? (
          <FlowGraph steps={chain.propagation_steps} selected={null} onSelect={() => {}} symbol={symbol} />
        ) : (
          <p className="text-sm text-slate-500">No propagation chain yet.</p>
        )}
      </SectionCard>
    </div>
  );
}
