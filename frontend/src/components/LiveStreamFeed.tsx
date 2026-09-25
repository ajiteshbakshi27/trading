"use client";
import { MessageSquare, Twitter } from "lucide-react";

export default function LiveStreamFeed({ posts }: { posts: any[] }) {
  return (
    <div className="glass rounded-2xl p-5">
      <div className="section-label mb-3 flex items-center justify-between">
        <span>Social stream · Reddit + X</span>
        {!!posts.length && <span className="tnum">{posts.length} posts</span>}
      </div>
      <div className="max-h-80 space-y-1.5 overflow-auto pr-1">
        {(posts || []).slice(0, 20).map((p: any, i: number) => {
          const isX = p.source === "X";
          return (
            <div key={i} className="rounded-xl px-3 py-2 text-sm transition-colors hover:bg-white/[0.04]">
              <div className="flex items-center justify-between gap-2 text-xs">
                <span className="flex items-center gap-1 text-slate-500">
                  {isX ? <Twitter className="h-3 w-3" /> : <MessageSquare className="h-3 w-3" />}
                  {p.source}
                </span>
                <span className={`tnum font-semibold ${p.sentiment > 0.2 ? "text-emerald-400" : p.sentiment < -0.2 ? "text-rose-400" : "text-slate-500"}`}>
                  {p.sentiment > 0 ? "+" : ""}{p.sentiment}
                </span>
              </div>
              <div className="mt-0.5 leading-snug text-slate-200">{p.text}</div>
              <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500">
                {(p.tickers || []).map((t: string) => (
                  <span key={t} className={`rounded px-1.5 py-px font-medium ${p.sentiment > 0.2 ? "bg-emerald-500/10 text-emerald-300" : p.sentiment < -0.2 ? "bg-rose-500/10 text-rose-300" : "bg-white/5 text-slate-400"}`}>${t}</span>
                ))}
                <span className="tnum ml-auto">▲{(p.upvotes || p.likes || 0).toLocaleString()}</span>
              </div>
            </div>
          );
        })}
        {!(posts || []).length && <p className="py-6 text-center text-sm text-slate-500">Waiting for feed…</p>}
      </div>
    </div>
  );
}
