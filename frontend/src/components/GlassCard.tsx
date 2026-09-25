import { motion } from "framer-motion";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export default function GlassCard({
  children,
  className,
  glow = "none",
}: {
  children: ReactNode;
  className?: string;
  glow?: "none" | "green" | "red";
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      whileHover={{ scale: 1.01 }}
      className={cn(
        "rounded-2xl border border-slate-800/80 bg-slate-900/60 backdrop-blur-xl",
        "transition-colors hover:border-slate-700/80",
        glow === "green" && "shadow-[0_0_24px_rgba(16,185,129,0.25)]",
        glow === "red" && "shadow-[0_0_24px_rgba(244,63,94,0.25)]",
        className
      )}
    >
      {children}
    </motion.div>
  );
}

/** Reusable pill button used across pages for consistent actions. */
export function PillButton({
  children, onClick, tone = "green", busy = false, disabled = false, className, title,
}: {
  children: ReactNode;
  onClick?: () => void;
  tone?: "green" | "red" | "blue" | "ghost";
  busy?: boolean;
  disabled?: boolean;
  className?: string;
  title?: string;
}) {
  const tones = {
    green: "bg-emerald-500 text-black hover:bg-emerald-400",
    red: "bg-rose-500 text-white hover:bg-rose-400",
    blue: "bg-blue-500 text-white hover:bg-blue-400",
    ghost: "bg-white/5 text-slate-300 ring-1 ring-white/10 hover:bg-white/10",
  } as const;
  return (
    <button onClick={onClick} disabled={disabled || busy} title={title}
      className={cn(
        "rounded-lg px-3 py-1.5 text-xs font-bold transition disabled:cursor-not-allowed disabled:opacity-50",
        tones[tone], className,
      )}>
      {busy ? "…" : children}
    </button>
  );
}
