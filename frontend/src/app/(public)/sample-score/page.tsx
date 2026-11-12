"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import CalibrationView from "@/components/parakh/CalibrationView";
import { ErrorBox, Loading } from "@/components/parakh/ui";

export default function SampleScorePage() {
  const [c, setC] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/api/parakh/public/sample-score").then(setC).catch((e) => setErr(e.message)); }, []);
  if (err) return <ErrorBox message={err} />;
  if (!c) return <Loading />;
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">{c.sample_label}</div>
      <CalibrationView c={c} checkHref="/try" />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
        <span>Your own score builds by itself: save your ideas with a confidence, and Parakh marks each one against real prices.</span>
        <Link href="/signup" className="rounded-lg bg-emerald-500 px-3 py-1.5 font-semibold text-black hover:bg-emerald-400">Sign up free</Link>
      </div>
    </div>
  );
}
