"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Menu, X, Settings, ChevronDown, ScanSearch } from "lucide-react";
import { useSession } from "@/lib/useSession";
import { AUTH_MODE, clearSession } from "@/lib/auth";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/check", label: "Check a trade" },
  { href: "/ideas", label: "My ideas" },
  { href: "/journal", label: "Journal" },
  { href: "/calibration", label: "Calibration" },
  { href: "/radar", label: "Hype radar" },
];

const MORE = [
  { href: "/events", label: "Event impact maps" },
  { href: "/options", label: "F&O analyser" },
  { href: "/strategy-lab", label: "Strategy backtests" },
  { href: "/leaderboard", label: "Leaderboard" },
];

/** Older experiments, kept reachable but out of the main flow. */
const LABS = [
  { href: "/dashboard", label: "US hype vs price" },
  { href: "/information-flow", label: "Information flow" },
  { href: "/thesis-lab", label: "Thesis stress lab" },
  { href: "/model-autopsy", label: "Model autopsy" },
  { href: "/research-lab", label: "Signal tournament" },
  { href: "/backtest", label: "Model backtest" },
  { href: "/demo", label: "Research demo" },
  { href: "/charts", label: "Charts" },
];

function Dropdown({ label, items, pathname }: { label: string; items: typeof MORE; pathname: string }) {
  return (
    <div className="group relative">
      <button className="flex items-center gap-1 hover:text-white">
        {label} <ChevronDown className="h-3 w-3" />
      </button>
      <div className="invisible absolute right-0 top-full z-50 mt-1 w-52 rounded-xl border border-slate-700/60 bg-[#0a0f1e] p-2 opacity-0 shadow-xl transition-all group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
        {items.map((n) => (
          <Link key={n.href} href={n.href}
            className={`block rounded-lg px-3 py-2 text-sm ${pathname === n.href ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300 hover:bg-white/5"}`}>
            {n.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const { session } = useSession();
  const router = useRouter();

  const signOut = async () => {
    await clearSession();
    router.push("/");
  };

  const link = (n: { href: string; label: string }, mobile = false) => (
    <Link key={n.href} href={n.href} onClick={() => setMobileOpen(false)}
      className={mobile
        ? `block rounded-lg px-3 py-2 text-sm ${pathname === n.href ? "bg-emerald-500/15 text-emerald-300" : "text-slate-300"}`
        : pathname === n.href ? "font-semibold text-white" : "hover:text-white"}>
      {n.label}
    </Link>
  );

  return (
    <nav className="sticky top-0 z-30 border-b border-slate-800/80 bg-[#030712]/85 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center gap-5 px-4 py-3">
        <Link href="/home" className="flex items-center gap-2 font-bold">
          <ScanSearch className="h-5 w-5 text-emerald-400" />
          <span>Parakh</span>
        </Link>

        <div className="hidden items-center gap-4 text-sm text-slate-300 lg:flex">
          {NAV.map((n) => link(n))}
          <Dropdown label="More" items={MORE} pathname={pathname} />
          <Dropdown label="Labs" items={LABS} pathname={pathname} />
        </div>

        <div className="ml-auto hidden items-center gap-2 lg:flex">
          {AUTH_MODE === "dev" && (
            <span className="rounded-full bg-amber-500/15 px-2.5 py-1 text-[11px] text-amber-300" title="No Supabase configured — local profile">
              Local dev mode
            </span>
          )}
          <Link href="/settings" title="Settings" className="rounded-lg p-2 text-slate-300 hover:bg-white/5">
            <Settings className="h-4 w-4" />
          </Link>
          {session && (
            <span className="flex items-center gap-1.5 rounded-full border border-slate-700/70 px-3 py-1 text-xs text-slate-300">
              <span className="max-w-[9rem] truncate">{session.name}</span>
              <button onClick={signOut} className="ml-1 text-slate-400 underline underline-offset-2 hover:text-white">
                Sign out
              </button>
            </span>
          )}
        </div>

        <button className="ml-auto rounded-lg p-2 text-slate-300 hover:bg-white/5 lg:hidden"
          onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle menu">
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="max-h-[80vh] overflow-auto border-t border-slate-800/60 bg-[#030712]/95 px-4 py-3 lg:hidden">
          <div className="space-y-1">{NAV.map((n) => link(n, true))}</div>
          <div className="mt-2 border-t border-slate-800/60 pt-2">{MORE.map((n) => link(n, true))}</div>
          <div className="mt-2 border-t border-slate-800/60 pt-2">
            <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">Labs</div>
            {LABS.map((n) => link(n, true))}
          </div>
          <div className="mt-2 flex items-center gap-2 border-t border-slate-800/60 pt-3">
            {link({ href: "/settings", label: "Settings" }, true)}
            {session && (
              <button onClick={signOut} className="rounded-lg bg-white/5 px-3 py-2 text-xs text-slate-300">
                Sign out ({session.name})
              </button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
}
