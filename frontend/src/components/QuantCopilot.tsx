"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, X, Send, Loader2 } from "lucide-react";
import { post } from "@/lib/api";

const SUGGESTIONS = [
  "Will HDFC Bank rally in 2 weeks?",
  "Why do my trades lose?",
  "How calibrated am I?",
  "What's hyped on my watchlist?",
];

type Msg = { role: "user" | "assistant"; content: string };

export default function QuantCopilot() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<string>("");

  const send = async (questionArg?: string) => {
    const question = (questionArg ?? q).trim();
    if (!question || busy) return;
    setQ(""); setBusy(true);
    const history = msgs;
    setMsgs((m) => [...m, { role: "user", content: question }]);
    try {
      const j = await post<any>("/api/parakh/copilot", { question, history });
      setMode(j.mode || "");
      setMsgs((m) => [...m, { role: "assistant", content: j.answer || "No answer." }]);
    } catch (e: any) {
      setMsgs((m) => [...m, { role: "assistant", content: e.message || "Server unreachable." }]);
    } finally { setBusy(false); }
  };

  return (
    <>
      <button onClick={() => setOpen(true)} title="Ask Parakh" aria-label="Open Parakh copilot"
        className="fixed bottom-5 right-5 z-40 rounded-full bg-emerald-500 p-3 text-black shadow-[0_0_20px_rgba(16,185,129,0.5)] transition hover:bg-emerald-400">
        <Bot className="h-5 w-5" />
      </button>
      <AnimatePresence>
        {open && (
          <motion.aside initial={{ x: 380 }} animate={{ x: 0 }} exit={{ x: 380 }}
            transition={{ type: "spring", damping: 28, stiffness: 260 }}
            className="fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-sm flex-col border-l border-slate-800/80 bg-slate-950/95 backdrop-blur-xl">
            <div className="flex items-center justify-between border-b border-slate-800/80 p-4">
              <div>
                <div className="flex items-center gap-2 font-bold"><Bot className="h-5 w-5 text-emerald-400" /> Ask Parakh</div>
                <div className="text-[11px] text-slate-500">
                  {mode === "claude" ? "Powered by Claude · reads your ideas & journal" : mode === "gemini" ? "Powered by Gemini · reads your ideas & journal" : "Analysis of your own ideas — not investment advice"}
                </div>
              </div>
              <button onClick={() => setOpen(false)} title="Close" className="rounded-lg p-1 hover:bg-white/10"><X className="h-5 w-5" /></button>
            </div>
            <div className="flex-1 space-y-2 overflow-auto p-4 text-sm">
              {msgs.length === 0 && (
                <div className="mr-8 rounded-xl bg-white/5 p-2.5">
                  Tell me a trade idea and I&apos;ll check it, or ask about your journal and calibration.
                </div>
              )}
              {msgs.map((m, i) => (
                <div key={i} className={`whitespace-pre-wrap rounded-xl p-2.5 ${m.role === "user" ? "ml-8 bg-emerald-500/15" : "mr-8 bg-white/5"}`}>
                  {m.content}
                </div>
              ))}
              {busy && (
                <div className="mr-8 flex items-center gap-2 rounded-xl bg-white/5 p-2.5 text-slate-400">
                  <Loader2 className="h-4 w-4 animate-spin" /> thinking…
                </div>
              )}
            </div>
            {msgs.length === 0 && (
              <div className="flex flex-wrap gap-1.5 border-t border-slate-800/80 px-3 pt-3">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)}
                    className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-300 hover:bg-white/10">{s}</button>
                ))}
              </div>
            )}
            <div className="flex gap-2 border-t border-slate-800/80 p-3">
              <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
                placeholder="Will Reliance fall after results?" aria-label="Your question"
                className="flex-1 rounded-lg bg-black/40 px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-emerald-500/50" />
              <button onClick={() => send()} disabled={busy} title="Send"
                className="rounded-lg bg-emerald-500 p-2 text-black transition hover:bg-emerald-400 disabled:opacity-50">
                <Send className="h-4 w-4" />
              </button>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
}
