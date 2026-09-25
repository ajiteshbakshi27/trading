"use client";
import { useEffect, useState } from "react";
import { Pause, Play } from "lucide-react";
import OrderBookDepth from "@/components/OrderBookDepth";
import { api } from "@/lib/api";

const SYMS = ["NVDA", "TSLA", "AAPL", "AMD", "MSFT", "GOOGL", "META", "INTC", "AMZN"];

export default function HFTPage() {
  const [books, setBooks] = useState<any[]>([]);
  const [sym, setSym] = useState("NVDA");
  const [paused, setPaused] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (paused) return;
    const tick = async () => {
      try {
        const j = await api<any>("/api/snapshot");
        setBooks(j.books || []);
        setErr("");
      } catch (e: any) { setErr(e.message || "Backend unreachable"); }
    };
    tick();
    const id = setInterval(tick, 1500);
    return () => clearInterval(id);
  }, [paused]);

  const book = books.find((b) => b.symbol === sym) || books[0];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">HFT Live Order Book & Microstructure</h1>
        <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ${
          err ? "bg-rose-500/15 text-rose-300" : "bg-emerald-500/15 text-emerald-300"}`}>
          <span className={`h-2 w-2 rounded-full ${err ? "bg-rose-500" : "animate-pulse bg-emerald-500"}`} />
          {err ? "OFFLINE" : paused ? "PAUSED" : "LIVE"}
        </span>
        <button onClick={() => setPaused((p) => !p)}
          className="ml-auto flex items-center gap-1.5 rounded-lg bg-white/5 px-3 py-1.5 text-xs text-slate-300 ring-1 ring-white/10 hover:bg-white/10">
          {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />} {paused ? "Resume" : "Pause"}
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {SYMS.map((s) => (
          <button key={s} onClick={() => setSym(s)}
            className={`rounded-lg px-3 py-1 text-sm ${s === sym ? "bg-green-500 text-black" : "glass"}`}>{s}</button>
        ))}
      </div>

      {err && <p className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 text-sm text-rose-300">{err}</p>}

      <div className="glass rounded-2xl p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="section-label mr-1">{book?.symbol || sym}</span>
          <span className="tnum rounded-lg bg-white/5 px-2.5 py-1 text-sm font-bold">${book?.mid}</span>
          <span className="tnum text-xs text-slate-400">spread {book?.spread_bps} bps</span>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${String(book?.ofi?.signal) === "BULLISH" ? "bg-emerald-500/10 text-emerald-300" : String(book?.ofi?.signal) === "BEARISH" ? "bg-rose-500/10 text-rose-300" : "bg-white/5 text-slate-400"}`}>
            OFI {book?.ofi?.ofi_norm} · {book?.ofi?.signal}
          </span>
          {book?.stream && !book.stream.stale && <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">● STREAM {book.stream.age_s}s</span>}
          {book?.stream?.stale && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">● STALE {book.stream.age_s}s</span>}
          {!book?.stream && book?.live && <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">● LIVE {book.live.change_pct}%</span>}
          {!book?.stream && !book?.live && <span className="rounded-full bg-white/5 px-2 py-0.5 text-xs text-slate-500">SIM</span>}
          {book?.arb?.opportunity && <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">ARB {book.arb.dislocation_bps} bps</span>}
        </div>
        <OrderBookDepth book={book} />
      </div>

      {!!books.length && (
        <div className="grid gap-3 md:grid-cols-3">
          {[
            ["Total books", String(books.length)],
            ["Arb opportunities", String(books.filter((b: any) => b.arb?.opportunity).length)],
            ["Bullish flow", String(books.filter((b: any) => b.ofi?.signal === "BULLISH").length)],
          ].map(([k, v]) => (
            <div key={k} className="glass rounded-2xl p-3">
              <div className="text-xs text-slate-400">{k}</div>
              <div className="text-lg font-bold tnum">{v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
