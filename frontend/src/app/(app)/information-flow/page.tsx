"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import FlowGraph, { FlowStep } from "@/components/research/FlowGraph";
import NodeDetail from "@/components/research/NodeDetail";
import { api } from "@/lib/api";
import { LAYER_META } from "@/lib/research";

type Chain = {
  event_id: string;
  symbol: string;
  event_type: string;
  detected_at: string;
  headline: string;
  sources: string[];
  propagation_steps: FlowStep[];
  confidence: number;
  span_s: number;
  layers_covered: string[];
  status: string;
  chain_mode: string;
  chain_mode_note: string;
  data_mode: string;
  data_mode_label: string;
  caveat: string;
};

export default function InformationFlowPage() {
  const [chains, setChains] = useState<Chain[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [node, setNode] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api<any>("/api/information/events?limit=20");
      setChains(res.events ?? []);
      setError("");
    } catch (e: any) {
      setError(e.message || "Failed to load events");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = chains.find((c) => c.event_id === activeId) ?? chains[0] ?? null;

  useEffect(() => {
    if (!active || !selected) {
      setNode(null);
      return;
    }
    api<any>(`/api/information/propagation/${active.event_id}/node/${selected}`)
      .then(setNode)
      .catch(() => setNode(null));
  }, [active, selected]);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 animate-pulse rounded bg-white/5" />
        <div className="h-96 animate-pulse rounded-2xl bg-white/5" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Research</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">
            Information Flow
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            When something happens, how does information move through the market
            layers before the price responds?
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            className="rounded-full bg-white/5 px-4 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/10"
          >
            Refresh
          </button>
          <DataModeBadge mode={active?.data_mode ?? "mock"} />
        </div>
      </header>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : !active ? (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
          <p className="text-sm text-slate-400">
            No events have been detected yet. Events open when a layer crosses
            its materiality threshold.
          </p>
          <button
            onClick={load}
            className="mt-4 rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-black hover:bg-emerald-400"
          >
            Check for events
          </button>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {chains.map((c) => (
              <button
                key={c.event_id}
                onClick={() => {
                  setActiveId(c.event_id);
                  setSelected(null);
                }}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  c.event_id === active.event_id
                    ? "bg-emerald-500 text-black"
                    : "bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                {c.symbol} · {c.event_type}
              </button>
            ))}
          </div>

          <SectionCard
            title={`${active.symbol} — propagation chain`}
            subtitle={active.headline}
            badge={
              <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[10px] font-semibold text-slate-400 ring-1 ring-white/10">
                {active.chain_mode === "observed"
                  ? "Observed timestamps"
                  : active.chain_mode === "simulated_sequence"
                    ? "Simulated sequence"
                    : "Mock"}
              </span>
            }
          >
            <FlowGraph
              steps={active.propagation_steps}
              selected={selected}
              onSelect={setSelected}
              symbol={active.symbol}
            />
            <p className="mt-2 text-[10px] text-slate-600">
              {active.chain_mode_note}
            </p>
          </SectionCard>

          <SectionCard
            title="Node detail"
            subtitle="Select a node above to inspect its raw signal, source and contribution."
          >
            <NodeDetail node={node} />
          </SectionCard>
        </>
      )}
    </div>
  );
}
