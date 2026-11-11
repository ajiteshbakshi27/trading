"use client";
import { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, CircleAlert, Info, Loader2, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function Card({ children, className, title, action }: {
  children: ReactNode; className?: string; title?: ReactNode; action?: ReactNode;
}) {
  return (
    <section className={cn("rounded-2xl border border-slate-800/80 bg-slate-900/60 p-4 backdrop-blur-xl sm:p-5", className)}>
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-semibold text-slate-200">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-400">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

const STATUS = {
  pass: { cls: "bg-emerald-500/15 text-emerald-300", Icon: CheckCircle2, label: "OK" },
  warn: { cls: "bg-amber-500/15 text-amber-300", Icon: CircleAlert, label: "Caution" },
  fail: { cls: "bg-rose-500/15 text-rose-300", Icon: XCircle, label: "Red flag" },
  info: { cls: "bg-sky-500/15 text-sky-300", Icon: Info, label: "Info" },
} as const;

export function StatusPill({ status }: { status: keyof typeof STATUS }) {
  const s = STATUS[status] || STATUS.info;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold", s.cls)}>
      <s.Icon className="h-3 w-3" /> {s.label}
    </span>
  );
}

const OUTCOME: Record<string, string> = {
  open: "bg-sky-500/15 text-sky-300", hit: "bg-emerald-500/15 text-emerald-300",
  miss: "bg-rose-500/15 text-rose-300", expired: "bg-slate-500/20 text-slate-300",
};

export function OutcomePill({ status }: { status: string }) {
  const label = { open: "Open", hit: "Target hit", miss: "Stopped out", expired: "Timed out" }[status] || status;
  return <span className={cn("rounded-full px-2 py-0.5 text-[11px] font-semibold", OUTCOME[status] || OUTCOME.expired)}>{label}</span>;
}

export function DataModeTag({ mode }: { mode?: string }) {
  if (!mode || mode === "live") {
    return <span className="rounded bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">Live data</span>;
  }
  return (
    <span title="Live NSE data was unavailable, so a deterministic simulated series is shown. Don't trade on it."
      className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-300">
      Simulated data
    </span>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "good" | "bad" | "neutral" }) {
  return (
    <div className="rounded-xl bg-white/[0.03] p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold tabular-nums",
        tone === "good" ? "text-emerald-300" : tone === "bad" ? "text-rose-300" : "text-white")}>{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-slate-500">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="flex items-center gap-2 py-6 text-sm text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> {label}</div>;
}

export function ErrorBox({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-200">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {message}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-700/70 p-6 text-center text-sm text-slate-400">{children}</div>;
}

export function Button({ children, onClick, busy, disabled, tone = "primary", type = "button", className }: {
  children: ReactNode; onClick?: () => void; busy?: boolean; disabled?: boolean;
  tone?: "primary" | "ghost" | "danger"; type?: "button" | "submit"; className?: string;
}) {
  const tones = {
    primary: "bg-emerald-500 text-black hover:bg-emerald-400",
    ghost: "bg-white/5 text-slate-200 ring-1 ring-white/10 hover:bg-white/10",
    danger: "bg-rose-500/90 text-white hover:bg-rose-500",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled || busy}
      className={cn("inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50", tones[tone], className)}>
      {busy && <Loader2 className="h-4 w-4 animate-spin" />} {children}
    </button>
  );
}

export const inputCls = "w-full rounded-lg border border-slate-700/70 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-slate-500 focus:border-emerald-500/60";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-medium text-slate-400">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}
    </label>
  );
}

export const inr = (x: number | null | undefined, d = 2) =>
  x == null || Number.isNaN(x) ? "—"
    : (x < 0 ? "−₹" : "₹") + Math.abs(Number(x)).toLocaleString("en-IN", { minimumFractionDigits: d, maximumFractionDigits: d });

export const pct = (x: number | null | undefined, d = 0, scale = 100) =>
  x == null ? "—" : `${(x * scale).toFixed(d)}%`;

export const signedPct = (x: number | null | undefined, d = 2) =>
  x == null ? "—" : `${x > 0 ? "+" : ""}${x.toFixed(d)}%`;
