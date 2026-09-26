"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, Radio, AlertTriangle, RefreshCw, FlaskConical } from "lucide-react";
import SignalCard from "@/components/SignalCard";
import OrderBookDepth from "@/components/OrderBookDepth";
import LiveStreamFeed from "@/components/LiveStreamFeed";
import SectionCard from "@/components/research/SectionCard";
import DataModeBadge from "@/components/research/DataModeBadge";
import EvidenceBar from "@/components/research/EvidenceBar";
import FlowGraph, { FlowStep } from "@/components/research/FlowGraph";
import { api, wsUrl } from "@/lib/api";
import { fmtConf } from "@/lib/research";

const FILTERS = ["ALL", "BET_FOR", "BET_AGAINST"] as const;

function Skeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="animate-pulse rounded-2xl border border-slate-800/60 bg-slate-900/40 p-4">
          <div className="h-5 w-24 rounded bg-white/10" />
          <div className="mt-3 h-7 w-32 rounded bg-white/10" />
          <div className="mt-2 h-3 w-full rounded bg-white/5" />
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [snap, setSnap] = useState<any>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("ALL");
  const [selected, setSelected] = useState<string | null>(null);
  const [cycle, setCycle] = useState<any>(null);
  const [cycleError, setCycleError] = useState("");
  const wsTries = useRef(0);

  const loadCycle = useCallback(async () => {
    try {
      const data = await api<any>("/api/research/cycle?symbol=NVDA&persist=false");
      setCycle(data);
      setCycleError("");
    } catch (e: any) {
      setCycleError(e.message || "Research cycle unavailable");
    }
  }, []);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let dead = false;

    const poll = async () => {
      try {
        const data = await api<any>("/api/snapshot");
        if (!dead) { setSnap(data); setError(""); }
      } catch (e: any) {
        if (!dead) setError(e.message || "Backend unreachable");
      }
    };

    const connect = () => {
      if (dead) return;
      try {
        ws = new WebSocket(wsUrl());
        ws.onmessage = (e) => {
          try {
            const m = JSON.parse(e.data);
            if (m.data) { setSnap(m.data); setError(""); }
          } catch {}
        };
        ws.onclose = () => {
          if (dead) return;
          const delay = Math.min(500 * 2 ** wsTries.current++, 8000);
          setTimeout(() => { if (!dead) { connect(); } }, delay);
        };
        ws.onopen = () => { wsTries.current = 0; };
      } catch {
        poll();
      }
    };

    connect();
    const id = setInterval(() => { if (!ws || ws.readyState !== 1) poll(); }, 5000);
    poll();
    loadCycle();
    return () => { dead = true; clearInterval(id); ws?.close(); };
  }, [loadCycle]);

  const signals = snap?.signals || [];
  const forSig = signals.filter((s: any) => s.type === "BET_FOR");
  const againstSig = signals.filter((s: any) => s.type === "BET_AGAINST");
  const shown = filter === "ALL" ? signals
    : signals.filter((s: any) => s.type === filter);
  const mode = snap?.market_data?.mode;
  const liveCount = (snap?.books || []).filter((b: any) => b.stream || b.live).length;
  const book = useMemo(
    () => (snap?.books || []).find((b: any) => b.symbol === (selected || "NVDA"))
      || (snap?.books || [])[0],
    [snap, selected]
  );

  const chainSteps: FlowStep[] = cycle?.chain?.propagation_steps ?? [];
  const thesis = cycle?.thesis ?? null;
  const stress = cycle?.stress ?? null;

  return (
    <div className="space-y-8">
      {snap?.halted && (
        <motion.div
          initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-rose-400" />
          <span>
            <b>Kill switch active</b>
            {snap?.kill?.reason ? ` — ${snap.kill.reason}` : ""}. Signals are halted;
            re-arm from the navbar to resume.
          </span>
        </motion.div>
      )}

      <motion.header
        initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
        className="flex flex-wrap items-end justify-between gap-4"
      >
        <div>
          <div className="section-label">QuantPulse AI · Live desk</div>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Signal Feed</h1>
          <p className="mt-1 max-w-xl text-sm text-slate-400">
            Quantum fair value × HFT order flow × crowd sentiment.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 ${
            error ? "bg-rose-500/10 text-rose-300 ring-rose-500/30"
                  : "bg-white/5 text-slate-300 ring-white/10"}`}>
            <Radio className={`h-3.5 w-3.5 ${error ? "text-rose-400" : "text-emerald-400"}`} />
            {error ? "Backend offline" : mode === "alpaca_stream" ? "Streaming" : mode === "alphavantage" ? "Live quotes" : "Simulator"}
            {!error && liveCount > 0 && <span className="tnum text-slate-400">· {liveCount}/{(snap?.books || []).length}</span>}
          </span>
          <button onClick={() => { setSnap(null); setError(""); (async () => { try { setSnap(await api("/api/snapshot")); } catch (e: any) { setError(e.message); } })(); }}
            title="Refresh snapshot"
            className="rounded-full bg-white/5 p-2 text-slate-300 ring-1 ring-white/10 hover:bg-white/10">
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
          <a href="/allocator"
            className="flex items-center gap-1.5 rounded-full bg-emerald-500 px-4 py-1.5 text-xs font-bold text-black shadow-[0_0_18px_rgba(16,185,129,0.35)] hover:bg-emerald-400">
            Allocator <ArrowRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </motion.header>

      {/* QuantPulse Signal + Evidence + Information Flow */}
      {cycle && !cycleError ? (
        <section className="grid gap-4 lg:grid-cols-3">
          <SectionCard
            title="QuantPulse Signal"
            subtitle={thesis ? `${thesis.symbol} · ${thesis.regime}` : "No signal yet"}
            badge={thesis ? (
              <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold ${
                thesis.direction === "LONG" ? "bg-emerald-500/15 text-emerald-300"
                : thesis.direction === "SHORT" ? "bg-rose-500/15 text-rose-300"
                : "bg-slate-500/15 text-slate-300"}`}>
                {thesis.direction}
              </span>
            ) : undefined}
          >
            {thesis ? (
              <div className="space-y-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold tabular-nums text-slate-100">
                    {fmtConf(thesis.confidence)}
                  </span>
                  <span className="text-xs text-slate-500">confidence</span>
                </div>
                {stress ? (
                  <p className="text-xs text-slate-400">
                    Robustness{" "}
                    <span className="font-semibold text-emerald-300">
                      {(stress.robustness * 100).toFixed(0)}%
                    </span>{" "}
                    · worst case{" "}
                    <span className="font-semibold text-rose-300">
                      {fmtConf(stress.worst_case_confidence)}
                    </span>
                  </p>
                ) : null}
                <a href="/thesis-lab" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-300 hover:text-emerald-200">
                  View thesis <ArrowRight className="h-3 w-3" />
                </a>
              </div>
            ) : (
              <p className="text-sm text-slate-500">No signal yet.</p>
            )}
          </SectionCard>

          <SectionCard title="Evidence" subtitle="Contribution to the fused signal">
            {thesis && thesis.evidence?.length > 0 ? (
              <EvidenceBar evidence={thesis.evidence} />
            ) : (
              <p className="text-sm text-slate-500">No evidence yet.</p>
            )}
          </SectionCard>

          <SectionCard
            title="Information Flow"
            subtitle="How information moved across layers"
            actions={
              <a href="/information-flow" className="inline-flex items-center gap-1 text-xs font-medium text-emerald-300 hover:text-emerald-200">
                Trace <ArrowRight className="h-3 w-3" />
              </a>
            }
          >
            {chainSteps.length > 0 ? (
              <div className="space-y-1.5">
                {chainSteps.slice(0, 5).map((s: FlowStep) => (
                  <div key={s.step_id} className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">{s.signal}</span>
                    <span className="tabular-nums text-slate-500">{s.lag_s}s</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">No propagation chain yet.</p>
            )}
          </SectionCard>
        </section>
      ) : null}

      {cycleError ? (
        <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 text-xs text-amber-200/80">
          Research cycle unavailable: {cycleError}
        </div>
      ) : null}

      <section>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="section-label">Signals</span>
          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">For {forSig.length}</span>
          <span className="rounded-full bg-rose-500/10 px-2 py-0.5 text-xs text-rose-300">Fade {againstSig.length}</span>
          <div className="ml-auto flex gap-1.5">
            {FILTERS.map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  filter === f ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>
                {f === "ALL" ? "All" : f === "BET_FOR" ? "Bet For" : "Fade"}
              </button>
            ))}
          </div>
        </div>
        {error && !snap ? (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/5 p-8 text-center">
            <p className="text-sm text-rose-300">{error}</p>
            <p className="mt-1 text-xs text-slate-500">
              Is the backend running? <code className="rounded bg-black/40 px-1">uvicorn app.main:app --port 8000</code>
            </p>
            <button onClick={() => { setError(""); pollNow(); }}
              className="mt-3 rounded-lg bg-emerald-500 px-4 py-1.5 text-xs font-bold text-black hover:bg-emerald-400">
              Retry
            </button>
          </div>
        ) : !snap ? <Skeleton /> : shown.length ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {shown.map((s: any, i: number) => <SignalCard key={s.symbol} signal={s} index={i}
              onSelect={() => setSelected(s.symbol)} />)}
          </div>
        ) : (
          <p className="rounded-2xl border border-slate-800/60 bg-slate-900/40 p-8 text-center text-sm text-slate-500">
            No signals match this filter right now.
          </p>
        )}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="glass rounded-2xl p-5">
          <div className="mb-3 flex items-center justify-between">
            <span className="section-label">Market microstructure{book?.symbol ? ` · ${book.symbol}` : ""}</span>
            <div className="flex gap-1">
              {["NVDA", "TSLA", "AAPL"].map((s) => (
                <button key={s} onClick={() => setSelected((cur) => (cur === s ? null : s))}
                  className={`rounded px-2 py-0.5 text-xs ${book?.symbol === s ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>
                  {s}
                </button>
              ))}
            </div>
          </div>
          <OrderBookDepth book={book} />
        </div>
        <LiveStreamFeed posts={snap?.sentiment?.posts || []} />
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <a href="/demo" className="glass group rounded-2xl p-5 transition-colors hover:bg-white/[0.06]">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-emerald-400" />
            <span className="section-label">Competition demo</span>
          </div>
          <p className="mt-2 text-sm text-slate-300">
            Run the complete loop: event → propagation → thesis → stress →
            prediction → outcome → autopsy → tournament.
          </p>
          <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-emerald-300 group-hover:text-emerald-200">
            Open demo <ArrowRight className="h-3 w-3" />
          </span>
        </a>
        <a href="/research-lab" className="glass group rounded-2xl p-5 transition-colors hover:bg-white/[0.06]">
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 text-cyan-400" />
            <span className="section-label">Research lab</span>
          </div>
          <p className="mt-2 text-sm text-slate-300">
            Controlled ablations of the fusion model. Does each information
            source actually contribute?
          </p>
          <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-cyan-300 group-hover:text-cyan-200">
            Open research lab <ArrowRight className="h-3 w-3" />
          </span>
        </a>
      </section>
    </div>
  );

  function pollNow() {
    api("/api/snapshot").then(setSnap).catch((e) => setError(e.message));
  }
}
