"use client";
import { useState } from "react";
import { motion } from "framer-motion";
import { TrendingUp, TrendingDown, Minus, ShoppingCart, ArrowDownRight, Bot } from "lucide-react";
import { api } from "@/lib/api";

export default function SignalCard({ signal, index = 0, onSelect }: {
  signal: any; index?: number; onSelect?: () => void;
}) {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const isLong = signal.direction === "LONG";
  const isShort = signal.direction === "SHORT";
  // Dynamic color system: emerald = buy/for, rose = sell/against/fade.
  const color = isLong
    ? "border-emerald-500/30 bg-emerald-500/[0.07] shadow-[0_0_24px_rgba(16,185,129,0.18)]"
    : isShort
      ? "border-rose-500/30 bg-rose-500/[0.07] shadow-[0_0_24px_rgba(244,63,94,0.18)]"
      : "border-slate-800/80 bg-slate-900/60";
  const badge = isLong
    ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/40"
    : isShort
      ? "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/40"
      : "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30";
  const Icon = isLong ? TrendingUp : isShort ? TrendingDown : Minus;

  const trade = async (side: "buy" | "sell") => {
    if (busy) return;
    const qty = prompt(`Quantity for ${signal.symbol} (${side}):`, "1");
    if (!qty) return;
    const n = Number(qty);
    if (!Number.isFinite(n) || n <= 0) { setMsg("Invalid quantity."); return; }
    setBusy(side); setMsg("");
    try {
      const j = await api<any>("/api/trade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol: signal.symbol, qty: n, side, order_type: "market" }),
      });
      setMsg(`${j.status === "ERROR" ? "Error" : "Filled"}: ${side} ${n} ${signal.symbol} (${j.status})`);
    } catch (e: any) {
      setMsg(e.message || "Order failed");
    } finally { setBusy(""); }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: Math.min(index * 0.05, 0.4) }}
      whileHover={{ scale: 1.015 }}
      className={`rounded-2xl border p-4 backdrop-blur-xl ${color}`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`rounded-lg p-1.5 ${isLong ? "bg-emerald-500/15" : isShort ? "bg-rose-500/15" : "bg-white/5"}`}>
            <Icon className="h-4 w-4" />
          </span>
          <button onClick={onSelect} disabled={!onSelect}
            className="tnum text-base font-bold tracking-tight hover:underline disabled:cursor-default disabled:no-underline"
            title={onSelect ? "Show order book" : undefined}>
            {signal.symbol}
          </button>
        </div>
        <span className={`whitespace-nowrap rounded-full px-2.5 py-1 text-[11px] font-semibold ${badge}`}>
          {signal.type.replace("_", " ")} · {signal.direction}
        </span>
      </div>
      <div className="tnum mt-3 flex items-baseline gap-1.5 text-sm">
        <span className="text-lg font-bold">${signal.price}</span>
        <span className="text-slate-400">→ ${signal.target}</span>
        <span className="ml-auto text-xs text-slate-500">stop ${signal.stop}</span>
      </div>
      <div className="mt-1 text-xs text-slate-400">
        Confidence {(signal.confidence * 100).toFixed(0)}% · Crowd {signal.bullish_pct}% · OFI {signal.ofi_norm}
      </div>
      <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-300">{signal.rationale}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-white/5 pt-3">
        <button onClick={() => trade("buy")} disabled={!!busy}
          className="flex items-center gap-1 rounded-lg bg-emerald-500 px-2.5 py-1 text-xs font-bold text-black transition hover:bg-emerald-400 disabled:opacity-50">
          <ShoppingCart className="h-3 w-3" /> {busy === "buy" ? "…" : "Buy"}
        </button>
        <button onClick={() => trade("sell")} disabled={!!busy}
          className="flex items-center gap-1 rounded-lg bg-rose-500 px-2.5 py-1 text-xs font-bold text-white transition hover:bg-rose-400 disabled:opacity-50">
          <ArrowDownRight className="h-3 w-3" /> {busy === "sell" ? "…" : "Fade"}
        </button>
        <a href="/prediction-bets" className="ml-auto flex items-center gap-1 rounded-lg bg-white/5 px-2.5 py-1 text-xs text-slate-300 transition hover:bg-white/10">
          <Bot className="h-3 w-3" /> Edges
        </a>
      </div>
      {msg && <p className={`mt-2 text-xs ${msg.startsWith("Error") || msg.includes("failed") || msg.includes("Invalid") ? "text-rose-400" : "text-emerald-400"}`}>{msg}</p>}
    </motion.div>
  );
}
