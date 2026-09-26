"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Activity, OctagonX, RotateCcw, Menu, X } from "lucide-react";
import { api, wsUrl } from "@/lib/api";
import { useSession } from "@/lib/useSession";
import { clearSession } from "@/lib/auth";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/hft-orderbook", label: "HFT Book" },
  { href: "/prediction-bets", label: "Prediction Bets" },
  { href: "/allocator", label: "Allocator" },
  { href: "/portfolio", label: "Portfolio" },
  { href: "/charts", label: "Charts" },
  { href: "/quantum-analytics", label: "Quantum" },
  { href: "/history", label: "History" },
];

const RESEARCH_NAV = [
  { href: "/information-flow", label: "Information Flow" },
  { href: "/thesis-lab", label: "Thesis Lab" },
  { href: "/model-autopsy", label: "Model Autopsy" },
  { href: "/research-lab", label: "Research Lab" },
  { href: "/backtest", label: "Backtest Lab" },
  { href: "/demo", label: "Demo" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [kill, setKill] = useState<any>({ halted: false });
  const [connected, setConnected] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const tries = useRef(0);
  const { session } = useSession();
  const router = useRouter();

  const signOut = () => {
    clearSession();
    router.push("/");
    router.refresh();
  };

  const refresh = async () => {
    try { setKill(await api<any>("/api/kill-switch")); } catch { /* offline */ }
  };

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    let ws: WebSocket | null = null;
    let dead = false;
    const connect = () => {
      if (dead) return;
      try {
        ws = new WebSocket(wsUrl());
        ws.onopen = () => { setConnected(true); tries.current = 0; };
        ws.onmessage = () => { setConnected(true); };
        ws.onclose = () => {
          setConnected(false);
          if (dead) return;
          setTimeout(connect, Math.min(1000 * 2 ** tries.current++, 10000));
        };
        ws.onerror = () => { try { ws?.close(); } catch {} };
      } catch { setConnected(false); }
    };
    connect();
    return () => { dead = true; clearInterval(id); ws?.close(); };
  }, []);

  const trip = async () => {
    if (!confirm("TRIP KILL SWITCH? Halts signals and liquidates live positions.")) return;
    try {
      await api("/api/kill-switch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "trip", reason: "manual navbar" }),
      });
    } catch {}
    refresh();
  };
  const rearm = async () => {
    try {
      await api("/api/kill-switch", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reset" }),
      });
    } catch {}
    refresh();
  };

  return (
    <nav className="sticky top-0 z-30 border-b border-slate-800/80 bg-[#030712]/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-4 px-4 py-3">
        <Link href="/dashboard" className="flex items-center gap-2 font-bold">
          <Activity className="h-5 w-5 text-emerald-400" />
          <span>QuantPulse AI</span>
        </Link>

        {/* Desktop nav */}
        <div className="hidden flex-wrap gap-4 text-sm text-slate-300 lg:flex">
          {NAV.map((n) => (
            <Link key={n.href} href={n.href}
              className={pathname === n.href ? "font-semibold text-white" : "hover:text-white"}>
              {n.label}
            </Link>
          ))}
          <div className="group relative">
            <button className="flex items-center gap-1 hover:text-white">
              Research
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div className="invisible absolute left-0 top-full z-50 mt-1 w-48 rounded-xl border border-slate-700/60 bg-[#0a0f1e] p-2 opacity-0 shadow-xl transition-all group-hover:visible group-hover:opacity-100">
              {RESEARCH_NAV.map((n) => (
                <Link key={n.href} href={n.href}
                  className={`block rounded-lg px-3 py-2 text-sm ${
                    pathname === n.href ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300 hover:bg-white/5"
                  }`}>
                  {n.label}
                </Link>
              ))}
            </div>
          </div>
          <Link href="/legal" className={pathname === "/legal" ? "font-semibold text-white" : "hover:text-white"}>
            Legal
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="ml-auto rounded-lg p-2 text-slate-300 hover:bg-white/5 lg:hidden"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>

        <div className="ml-auto hidden items-center gap-2 lg:flex">
          {session && (
            <span className="flex items-center gap-1.5 rounded-full border border-slate-700/70 px-3 py-1 text-xs text-slate-300">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span className="max-w-[9rem] truncate">{session.name}</span>
              <button onClick={signOut} className="ml-1 text-slate-400 underline underline-offset-2 hover:text-white">
                Sign out
              </button>
            </span>
          )}
          <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ${
            connected
              ? "bg-emerald-500/15 text-emerald-300"
              : "bg-rose-500/15 text-rose-300"}`}>
            <span className={`h-2 w-2 rounded-full ${
              connected
                ? "animate-pulse bg-emerald-500 shadow-[0_0_12px_#10B981]"
                : "bg-rose-500"}`} />
            {connected ? "LIVE" : "OFFLINE"}
          </span>
          {kill.halted ? (
            <button onClick={rearm} title="Re-arm signal generation"
              className="flex items-center gap-1 rounded-lg bg-amber-500 px-3 py-1 text-xs font-bold text-black hover:bg-amber-400">
              <RotateCcw className="h-3 w-3" /> HALTED — RE-ARM
            </button>
          ) : (
            <button onClick={trip} title="Emergency kill switch"
              className="flex items-center gap-1 rounded-lg bg-rose-600 px-3 py-1 text-xs font-bold text-white shadow-[0_0_16px_rgba(244,63,94,0.5)] hover:bg-rose-500">
              <OctagonX className="h-3.5 w-3.5" /> KILL SWITCH
            </button>
          )}
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className="border-t border-slate-800/60 bg-[#030712]/95 px-4 py-3 lg:hidden">
          <div className="space-y-1">
            {NAV.map((n) => (
              <Link key={n.href} href={n.href}
                onClick={() => setMobileOpen(false)}
                className={`block rounded-lg px-3 py-2 text-sm ${
                  pathname === n.href ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300"
                }`}>
                {n.label}
              </Link>
            ))}
          </div>
          <div className="mt-2 border-t border-slate-800/60 pt-2">
            <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Research
            </div>
            <div className="space-y-1">
              {RESEARCH_NAV.map((n) => (
                <Link key={n.href} href={n.href}
                  onClick={() => setMobileOpen(false)}
                  className={`block rounded-lg px-3 py-2 text-sm ${
                    pathname === n.href ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300"
                  }`}>
                  {n.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="mt-2 border-t border-slate-800/60 pt-2">
            <Link href="/legal" onClick={() => setMobileOpen(false)}
              className="block rounded-lg px-3 py-2 text-sm text-slate-300">
              Legal
            </Link>
          </div>
          <div className="mt-3 flex items-center gap-2 border-t border-slate-800/60 pt-3">
            {session && (
              <button onClick={signOut} className="rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-300">
                Sign out ({session.name})
              </button>
            )}
            <span className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ${
              connected ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
              {connected ? "LIVE" : "OFFLINE"}
            </span>
            {kill.halted ? (
              <button onClick={rearm} className="rounded-lg bg-amber-500 px-3 py-1 text-xs font-bold text-black">
                RE-ARM
              </button>
            ) : (
              <button onClick={trip} className="rounded-lg bg-rose-600 px-3 py-1 text-xs font-bold text-white">
                KILL
              </button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
