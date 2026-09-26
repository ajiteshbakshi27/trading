"use client";
import { useCallback, useEffect, useState } from "react";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import FlowGraph, { FlowStep } from "@/components/research/FlowGraph";
import StressLab from "@/components/research/StressLab";
import AutopsyReport from "@/components/research/AutopsyReport";
import TournamentMatrix from "@/components/research/TournamentMatrix";
import { api } from "@/lib/api";

type DemoBeat = {
  step: string;
  key: string;
  title: string;
  body: string;
};

type CycleResult = {
  status: string;
  scenario_id: string;
  scenario_label: string;
  event: any;
  chain: any;
  thesis: any;
  stress: any;
  prediction: any;
  outcome: any;
  autopsy: any;
  tournament: { results: any[]; matrix: any; window: any; methodology: any };
  data_mode: string;
  data_mode_label: string;
};

export default function DemoPage() {
  const [beats, setBeats] = useState<DemoBeat[]>([]);
  const [activeStep, setActiveStep] = useState(1);
  const [cycle, setCycle] = useState<CycleResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<any>("/api/demo")
      .then((res) => setBeats(res.beats ?? []))
      .catch((e) => setError(e.message));
  }, []);

  const run = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api<CycleResult>("/api/demo/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persist: true }),
      });
      setCycle(res);
      setActiveStep(11);
    } catch (e: any) {
      setError(e.message || "Demo run failed");
    } finally {
      setLoading(false);
    }
  }, []);

  const cycleForStep = (step: number): Partial<CycleResult> | null => {
    if (!cycle) return null;
    const map: Record<string, keyof CycleResult> = {
      event: "event",
      chain: "chain",
      thesis: "thesis",
      stress: "stress",
      prediction: "prediction",
      outcome: "outcome",
      autopsy: "autopsy",
      tournament: "tournament",
    };
    const beat = beats.find((b) => Number(b.step) === step);
    if (!beat) return null;
    return { [map[beat.key]]: cycle[map[beat.key]] } as Partial<CycleResult>;
  };

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="section-label">QuantPulse AI · Demo</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">
            Competition Demo
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            A deterministic, self-contained walkthrough of the complete loop:
            event → propagation → thesis → stress → prediction → outcome →
            autopsy → tournament.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={run}
            disabled={loading}
            className="rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-bold text-black shadow-[0_0_18px_rgba(16,185,129,0.35)] hover:bg-emerald-400 disabled:opacity-50"
          >
            {loading ? "Running…" : "Run full demo"}
          </button>
          <DataModeBadge mode={cycle?.data_mode ?? "simulated"} />
        </div>
      </header>

      <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200/90">
        <strong>SIMULATED SCENARIO.</strong> This demo runs on synthetic data.
        No real market data is used, and nothing here is a real historical
        event.
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center text-sm text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {beats.map((beat) => (
          <button
            key={beat.step}
            onClick={() => setActiveStep(Number(beat.step))}
            className={`rounded-xl border p-3 text-left transition-all ${
              activeStep === Number(beat.step)
                ? "border-emerald-500/40 bg-emerald-500/10"
                : "border-slate-700/50 bg-white/[0.02] hover:bg-white/[0.05]"
            }`}
          >
            <div className="text-[10px] font-semibold tabular-nums text-slate-500">
              {beat.step}
            </div>
            <div className="mt-0.5 text-xs font-semibold text-slate-200">
              {beat.title}
            </div>
          </button>
        ))}
      </div>

      {activeStep === 1 && !cycle ? (
        <SectionCard
          title="Run the demo"
          subtitle="Click the button above to walk through the complete loop."
        >
          <p className="text-sm text-slate-400">
            The demo takes about 2–3 minutes and covers all eleven beats. Every
            record it produces is labelled SIMULATED.
          </p>
        </SectionCard>
      ) : (
        <SectionCard
          title={`Step ${activeStep} — ${beats.find((b) => Number(b.step) === activeStep)?.title ?? ""}`}
          subtitle={beats.find((b) => Number(b.step) === activeStep)?.body}
        >
          {!cycle ? (
            <p className="text-sm text-slate-500">
              Run the demo to populate this step.
            </p>
          ) : null}

          {activeStep === 3 && cycle?.chain ? (
            <FlowGraph
              steps={cycle.chain.propagation_steps ?? []}
              selected={null}
              onSelect={() => {}}
              symbol={cycle.event?.symbol ?? "NVDA"}
            />
          ) : null}

          {activeStep === 4 && cycle?.chain ? (
            <div className="space-y-2">
              {(cycle.chain.propagation_steps ?? []).map((s: FlowStep) => (
                <div
                  key={s.step_id}
                  className="flex items-center justify-between rounded-lg border border-slate-700/50 bg-white/[0.02] px-3 py-2 text-xs"
                >
                  <span className="font-medium text-slate-300">
                    {s.signal}
                  </span>
                  <span className="tabular-nums text-slate-500">
                    {s.lag_s}s
                  </span>
                </div>
              ))}
            </div>
          ) : null}

          {activeStep === 5 && cycle?.thesis ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Direction
                </div>
                <div className="mt-1 text-lg font-bold text-emerald-300">
                  {cycle.thesis.direction}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Confidence
                </div>
                <div className="mt-1 text-lg font-bold tabular-nums text-slate-100">
                  {(cycle.thesis.confidence * 100).toFixed(1)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Regime
                </div>
                <div className="mt-1 text-lg font-bold text-slate-100">
                  {cycle.thesis.regime}
                </div>
              </div>
            </div>
          ) : null}

          {activeStep === 6 && cycle?.stress ? (
            <StressLab stress={cycle.stress} />
          ) : null}

          {activeStep === 7 && cycle?.prediction ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Direction
                </div>
                <div className="mt-1 text-lg font-bold text-emerald-300">
                  {cycle.prediction.direction}
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Expected move
                </div>
                <div className="mt-1 text-lg font-bold tabular-nums text-emerald-300">
                  {cycle.prediction.expected_move_pct > 0 ? "+" : ""}
                  {cycle.prediction.expected_move_pct.toFixed(2)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Horizon
                </div>
                <div className="mt-1 text-lg font-bold text-slate-100">
                  {cycle.prediction.horizon}
                </div>
              </div>
            </div>
          ) : null}

          {activeStep === 8 && cycle?.outcome ? (
            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Expected
                </div>
                <div className="mt-1 text-lg font-bold tabular-nums text-emerald-300">
                  {cycle.outcome.expected_move_pct > 0 ? "+" : ""}
                  {cycle.outcome.expected_move_pct.toFixed(2)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Actual
                </div>
                <div className="mt-1 text-lg font-bold tabular-nums text-rose-300">
                  {cycle.outcome.actual_move_pct > 0 ? "+" : ""}
                  {cycle.outcome.actual_move_pct.toFixed(2)}%
                </div>
              </div>
              <div className="rounded-xl border border-slate-700/50 bg-white/[0.03] p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-500">
                  Correct
                </div>
                <div
                  className={`mt-1 text-lg font-bold ${
                    cycle.outcome.correct ? "text-emerald-300" : "text-rose-300"
                  }`}
                >
                  {cycle.outcome.correct ? "Yes" : "No"}
                </div>
              </div>
            </div>
          ) : null}

          {activeStep === 9 && cycle?.autopsy ? (
            <AutopsyReport autopsy={cycle.autopsy} />
          ) : null}

          {activeStep === 10 && cycle?.tournament ? (
            <div className="space-y-3">
              <TournamentMatrix matrix={cycle.tournament.matrix} />
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {cycle.tournament.results.map((r: any) => (
                  <div
                    key={r.experiment_id}
                    className="rounded-xl border border-slate-700/50 bg-white/[0.02] p-3"
                  >
                    <div className="text-[10px] font-semibold text-slate-300">
                      {r.name}
                    </div>
                    <div className="mt-1 text-sm font-bold tabular-nums text-slate-100">
                      {r.overall?.directional_accuracy != null
                        ? `${(r.overall.directional_accuracy * 100).toFixed(1)}%`
                        : "—"}
                    </div>
                    <div className="text-[10px] tabular-nums text-slate-500">
                      n={r.overall?.n ?? 0}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeStep === 11 && cycle ? (
            <div className="space-y-3">
              <p className="text-sm text-slate-300">
                The demo walked the complete loop. The tournament matrix shows
                <strong> insufficient data</strong> because the sample is below
                the required floor — so no numbers were reported.
              </p>
              <div className="rounded-xl border border-slate-700/50 bg-black/20 p-4 text-xs text-slate-400">
                <p>
                  <strong>Research conclusions.</strong> The fusion model produced
                  a {cycle.thesis.direction} thesis at{" "}
                  {(cycle.thesis.confidence * 100).toFixed(1)}% confidence. The
                  stress test showed robustness{" "}
                  {(cycle.stress.robustness * 100).toFixed(0)}%. The prediction
                  resolved {cycle.outcome.correct ? "correctly" : "incorrectly"},
                  and the autopsy identified{" "}
                  {cycle.autopsy.failure_mode?.replace(/_/g, " ") ??
                    "no specific failure mode"}
                  . The tournament could not report performance because the
                  sample size was insufficient.
                </p>
                <p className="mt-2 text-slate-500">
                  These are measurements inside QuantPulse's fusion function on
                  a synthetic window. They do not constitute predictive edge in
                  any market.
                </p>
              </div>
            </div>
          ) : null}
        </SectionCard>
      )}
    </div>
  );
}
