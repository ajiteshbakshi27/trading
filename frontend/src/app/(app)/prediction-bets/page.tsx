"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import SectionCard from "@/components/research/SectionCard";

// Phase 3: vibrant-red edge styling. |edge| >= HOT_EDGE gets solid
// high-contrast red; smaller edges get red glow outline.
const HOT_EDGE = 0.12;

function isHot(e: any) {
  return Math.abs(e.edge ?? 0) >= HOT_EDGE || (e.confidence ?? 0) >= 0.8;
}

function EventTransmissionEmbed() {
  const [events, setEvents] = useState<any[]>([]);
  const [graph, setGraph] = useState<any>(null);
  useEffect(() => {
    api<any>("/api/events?limit=5")
      .then((res) => {
        setEvents(res.events ?? []);
        const first = res.events?.[0];
        if (first) {
          api<any>(`/api/events/${first.event_id}/assets`)
            .then((g) => setGraph(g))
            .catch(() => setGraph(null));
        }
      })
      .catch(() => setEvents([]));
  }, []);
  if (!graph) return null;
  return (
    <SectionCard
      title="Event → asset transmission"
      subtitle="How an event maps to themes and potentially affected assets"
    >
      <div className="space-y-2 text-xs">
        {graph.exposures?.slice(0, 5).map((e: any) => (
          <div key={e.symbol} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2">
            <span className="font-semibold text-slate-200">{e.symbol}</span>
            <span className="text-slate-500">{e.relation}</span>
            <span className="tabular-nums text-slate-400">
              {e.median_response_pct != null
                ? `${e.median_response_pct > 0 ? "+" : ""}${e.median_response_pct.toFixed(2)}%`
                : "insufficient data"}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[10px] text-slate-600">
        Relationships are observed co-occurrence, not causation.
      </p>
    </SectionCard>
  );
}

export default function PredictionPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<{ key: string; text: string; ok: boolean } | null>(null);

  useEffect(() => {
    const f = async () => {
      try { setData(await api<any>("/api/snapshot")); setErr(""); }
      catch (e: any) { setErr(e.message || "Backend unreachable"); }
    };
    f(); const id = setInterval(f, 4000);
    return () => clearInterval(id);
  }, []);

  const trade = async (symbol: string, side: string) => {
    if (busy) return;
    const qty = prompt(`Quantity for ${symbol} (${side}):`, "1");
    if (!qty) return;
    const n = Number(qty);
    if (!Number.isFinite(n) || n <= 0) { setMsg({ key: symbol, text: "Invalid quantity.", ok: false }); return; }
    setBusy(symbol);
    try {
      const j = await api<any>("/api/trade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, qty: n, side, order_type: "market" }),
      });
      setMsg({ key: symbol, text: `${side} ${n} ${symbol}: ${j.status}`, ok: j.status !== "ERROR" });
    } catch (e: any) {
      setMsg({ key: symbol, text: e.message || "Order failed", ok: false });
    } finally { setBusy(""); }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Prediction Markets & Fade-Crowd Tracker</h1>

      {err && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-300">{err}</p>}
      {!data && !err && <p className="text-sm text-slate-500">Loading markets…</p>}

      <div className="glass rounded-2xl border-red-500/20 p-4">
        <h2 className="mb-2 font-semibold text-red-400">Mispriced Edges (Quantum vs Crowd)</h2>
        <div className="space-y-2">
          {(data?.prediction?.edges || []).map((e: any) => {
            const hot = isHot(e);
            return (
              <div
                key={e.id}
                className={`flex items-center justify-between rounded-xl border p-3 ${
                  hot
                    ? "border-red-500/70 bg-red-500/15 shadow-[0_0_18px_rgba(239,68,68,0.45)]"
                    : "border-red-500/30 bg-red-500/5 shadow-[0_0_10px_rgba(239,68,68,0.15)]"
                }`}
              >
                <div>
                  <div className="font-medium">{e.question}</div>
                  <div className="text-xs text-slate-400">
                    Crowd {(e.crowd_prob*100).toFixed(1)}% → Quantum {(e.quantum_prob*100).toFixed(1)}% ·{" "}
                    <span className="font-bold text-red-400">
                      {e.edge > 0 ? "+" : ""}{(e.edge*100).toFixed(1)}pp edge
                    </span>
                  </div>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-xs font-bold ${
                    hot
                      ? "bg-red-500 text-white shadow-[0_0_12px_rgba(239,68,68,0.8)]"
                      : "bg-red-500/20 text-red-300"
                  }`}
                >
                  {e.side} ({(e.confidence*100).toFixed(0)}%)
                </span>
              </div>
            );
          })}
          {data && !(data?.prediction?.edges||[]).length && <p className="text-sm text-slate-500">No edges above threshold.</p>}
        </div>
      </div>

      <EventTransmissionEmbed />

      <div className="glass rounded-2xl p-4">
        <h2 className="mb-2 font-semibold">All Markets</h2>
        <table className="w-full text-sm">
          <thead className="text-slate-400"><tr><th className="text-left">Market</th><th>Crowd</th><th>Quantum</th><th>Edge</th></tr></thead>
          <tbody>{(data?.prediction?.markets||[]).map((m:any)=>{
            const edge = (m.quantum_prob ?? m.crowd_prob) - m.crowd_prob;
            const hot = Math.abs(edge) >= HOT_EDGE;
            return (
              <tr key={m.id} className={`border-t border-white/5 ${hot ? "bg-red-500/10" : ""}`}>
                <td className="py-2">{m.question}</td><td>{(m.crowd_prob*100).toFixed(1)}%</td>
                <td>{(m.quantum_prob*100).toFixed(1)}%</td>
                <td className={`font-semibold ${hot ? "text-red-300" : "text-red-400"}`}>
                  {(edge*100).toFixed(1)}%</td>
              </tr>
            );
          })}
          {data && !(data?.prediction?.markets||[]).length && (
            <tr><td colSpan={4} className="py-6 text-center text-slate-500">No markets loaded.</td></tr>
          )}</tbody>
        </table>
      </div>

      <div className="glass rounded-2xl p-4">
        <h2 className="mb-2 font-semibold text-rose-300">Active Fade-Crowd Signals</h2>
        <div className="grid gap-2 md:grid-cols-2">
          {(data?.signals||[]).filter((s:any)=>s.type==="BET_AGAINST").map((s:any)=>(
            <div key={s.symbol} className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 shadow-[0_0_14px_rgba(244,63,94,0.2)]">
              <div className="flex items-center justify-between gap-2">
                <div className="font-bold">FADE {s.symbol} → {s.direction}</div>
                <div className="flex gap-1.5">
                  <button onClick={() => trade(s.symbol, "sell")} disabled={!!busy}
                    className="rounded-lg bg-rose-500 px-2.5 py-1 text-xs font-bold text-white transition hover:bg-rose-400 disabled:opacity-50">
                    {busy === s.symbol ? "…" : "Short"}
                  </button>
                  <button onClick={() => trade(s.symbol, "buy")} disabled={!!busy}
                    className="rounded-lg bg-white/10 px-2.5 py-1 text-xs font-bold text-slate-200 transition hover:bg-white/20 disabled:opacity-50">
                    Buy
                  </button>
                </div>
              </div>
              <div className="mt-1 text-xs text-slate-300">{s.rationale}</div>
              {msg?.key === s.symbol && (
                <div className={`mt-1.5 text-xs ${msg?.ok ? "text-emerald-400" : "text-rose-400"}`}>{msg?.text}</div>
              )}
            </div>
          ))}
          {data && !(data?.signals||[]).some((s:any)=>s.type==="BET_AGAINST") && (
            <p className="text-sm text-slate-500">No fade signals right now.</p>
          )}
        </div>
      </div>
    </div>
  );
}
