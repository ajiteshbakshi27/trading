"use client";
import { useState } from "react";
import Link from "next/link";
import { post } from "@/lib/api";
import ThesisReport from "@/components/parakh/ThesisReport";
import { Button, Card, ErrorBox, Loading, PageHeader, inputCls } from "@/components/parakh/ui";

const EXAMPLES = [
  "Bank Nifty will rally after the RBI policy, 2 weeks, 70% sure",
  "HDFC Bank will break out and rise over 3 weeks, 65% sure",
  "I think Infosys will fall after results in 5 days",
];

export default function TryPage() {
  const [idea, setIdea] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [report, setReport] = useState<any>(null);

  const run = async () => {
    setErr(""); setBusy(true); setReport(null);
    try { setReport(await post("/api/parakh/public/check", { idea, save: false })); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader title="Check a trade idea"
        subtitle="Describe the trade you're thinking about, in your own words. Parakh tests it against price history and the odds before you put money on it. No sign-up needed for a few tries." />
      <Card>
        <textarea value={idea} onChange={(e) => setIdea(e.target.value)} rows={3} maxLength={1000}
          placeholder="e.g. Reliance will rally after its results, 2 weeks, 75% sure"
          aria-label="Your trade idea" className={inputCls + " resize-y text-base"} />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((e) => (
            <button key={e} onClick={() => setIdea(e)} className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-400 hover:bg-white/10">{e}</button>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={run} busy={busy} disabled={!idea.trim()}>Check it</Button>
          <span className="text-xs text-slate-500">Trial: nothing is saved or tracked.</span>
        </div>
      </Card>
      <div className="mt-4"><ErrorBox message={err} /></div>
      {busy && <Loading label="Running checks, simulations and the stress test…" />}
      {report && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
            <span>Sign up and Parakh will track this idea, mark it hit or stopped by itself, and score your confidence over time.</span>
            <Link href="/signup" className="rounded-lg bg-emerald-500 px-3 py-1.5 font-semibold text-black hover:bg-emerald-400">Sign up free</Link>
          </div>
          <ThesisReport r={report} />
        </div>
      )}
    </div>
  );
}
