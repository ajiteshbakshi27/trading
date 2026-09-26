"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import StressLab from "@/components/research/StressLab";
import EvidenceBar from "@/components/research/EvidenceBar";
import { api } from "@/lib/api";
import { fmtConf } from "@/lib/research";

type Thesis = {
  thesis_id: string;
  signal_id: string;
  symbol: string;
  direction: string;
  confidence: number;
  fused_score: number;
  evidence: Array<{
    feature: string;
    z_score: number;
    contribution: number;
    confidence: number;
    data_mode?: string;
  }>;
  contradictions: Array<{
    evidence_id: string;
    layer: string;
    feature: string;
    reason: string;
    z_score: number;
  }>;
  regime: string;
  created_at: string;
  data_mode: string;
  plain_language: string;
};

export default function ThesisLabPage() {
  const [theses, setTheses] = useState<Thesis[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [stress, setStress] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const res = await api<any>("/api/thesis/theses?limit=50");
      setTheses(res.theses ?? []);
      setError("");
    } catch (e: any) {
      setError(e.message || "Failed to load theses");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const active = theses.find((t) => t.thesis_id === activeId) ?? theses[0] ?? null;

  useEffect(() => {
    if (!active) {
      setStress(null);
      return;
    }
    api<any>(`/api/thesis/${active.thesis_id}/stress-test?persist=true`)
      .then(setStress)
      .catch(() => setStress(null));
  }, [active]);

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
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Thesis Lab</h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Every signal becomes a testable thesis. Then we attack it.
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
            No thesis has been generated yet. A thesis is produced when the
            fusion engine combines evidence into a direction and a confidence.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {theses.map((t) => (
              <button
                key={t.signal_id}
                onClick={() => setActiveId(t.signal_id)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  t.signal_id === active.signal_id
                    ? "bg-emerald-500 text-black"
                    : "bg-white/5 text-slate-300 hover:bg-white/10"
                }`}
              >
                {t.symbol} · {t.direction} · {fmtConf(t.confidence)}
              </button>
            ))}
          </div>

          <SectionCard
            title={`${active.symbol} — thesis`}
            subtitle={active.plain_language}
            badge={
              <span
                className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                  active.direction === "LONG"
                    ? "bg-emerald-500/15 text-emerald-300"
                    : active.direction === "SHORT"
                      ? "bg-rose-500/15 text-rose-300"
                      : "bg-slate-500/15 text-slate-300"
                }`}
              >
                {active.direction}
              </span>
            }
          >
            <div className="mb-4 grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Confidence
                </div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {fmtConf(active.confidence)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Fused score
                </div>
                <div className="mt-1 text-xl font-bold tabular-nums text-slate-100">
                  {active.fused_score > 0 ? "+" : ""}
                  {active.fused_score.toFixed(3)}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Regime
                </div>
                <div className="mt-1 text-xl font-bold text-slate-100">
                  {active.regime}
                </div>
              </div>
            </div>

            <h4 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Evidence
            </h4>
            <EvidenceBar evidence={active.evidence} />

            {active.contradictions.length > 0 ? (
              <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
                  Contradictions
                </h4>
                <ul className="list-inside list-disc space-y-0.5 text-xs text-amber-200/80">
                  {active.contradictions.map((c) => (
                    <li key={c.evidence_id}>{c.reason}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </SectionCard>

          <SectionCard
            title="Stress test"
            subtitle="Perturb the evidence under explicit rules and re-run the same fusion."
            actions={
              <button
                onClick={() =>
                  active &&
                  api<any>(`/api/thesis/${active.signal_id}/stress-test?persist=true`)
                    .then(setStress)
                    .catch(() => {})
                }
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-bold text-black hover:bg-emerald-400"
              >
                Run stress test
              </button>
            }
          >
            <StressLab stress={stress} />
          </SectionCard>
        </>
      )}
    </div>
  );
}
