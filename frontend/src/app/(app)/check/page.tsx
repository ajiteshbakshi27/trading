"use client";
import { useState } from "react";
import Link from "next/link";
import { post } from "@/lib/api";
import ThesisReport from "@/components/parakh/ThesisReport";
import { Button, Card, ErrorBox, Field, Loading, PageHeader, inputCls } from "@/components/parakh/ui";

const EXAMPLES = [
  "Bank Nifty will rally after the RBI policy, 2 weeks, 70% sure",
  "HDFC Bank will break out and rise over 3 weeks, 65% sure",
  "I think Infosys will fall after results in 5 days",
];

export default function CheckPage() {
  const [idea, setIdea] = useState("");
  const [adv, setAdv] = useState(false);
  const [f, setF] = useState<any>({ symbol: "", direction: "", horizon_days: "", user_confidence: "", target_price: "", stop_price: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [report, setReport] = useState<any>(null);

  const run = async () => {
    setErr(""); setBusy(true); setReport(null);
    const body: any = { idea, save: true };
    for (const [k, v] of Object.entries(f)) if (v !== "") body[k] = ["symbol", "direction"].includes(k) ? v : Number(v);
    if (body.user_confidence && body.user_confidence > 1) body.user_confidence = body.user_confidence / 100;
    try { setReport(await post("/api/parakh/check", body)); }
    catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader title="Check a trade" subtitle="Describe the trade you're thinking about, in your own words. Parakh tests it against price history, the odds and its own stress rules — before you put money on it." />
      <Card>
        <textarea value={idea} onChange={(e) => setIdea(e.target.value)} rows={3} maxLength={1000}
          placeholder="e.g. Reliance will rally after its results, 2 weeks, 75% sure"
          aria-label="Your trade idea" className={inputCls + " resize-y text-base"} />
        <div className="mt-2 flex flex-wrap gap-1.5">
          {EXAMPLES.map((e) => (
            <button key={e} onClick={() => setIdea(e)} className="rounded-full bg-white/5 px-2.5 py-1 text-xs text-slate-400 hover:bg-white/10">{e}</button>
          ))}
        </div>
        <button onClick={() => setAdv(!adv)} className="mt-3 text-xs text-slate-400 underline underline-offset-2">
          {adv ? "Hide" : "Set"} exact levels (optional)
        </button>
        {adv && (
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Field label="NSE symbol"><input className={inputCls} value={f.symbol} onChange={(e) => setF({ ...f, symbol: e.target.value.toUpperCase() })} placeholder="RELIANCE" /></Field>
            <Field label="Direction">
              <select className={inputCls} value={f.direction} onChange={(e) => setF({ ...f, direction: e.target.value })}>
                <option value="">From text</option><option value="LONG">Rise (long)</option><option value="SHORT">Fall (short)</option>
              </select>
            </Field>
            <Field label="Days"><input type="number" min={1} max={120} className={inputCls} value={f.horizon_days} onChange={(e) => setF({ ...f, horizon_days: e.target.value })} /></Field>
            <Field label="Confidence %"><input type="number" min={50} max={99} className={inputCls} value={f.user_confidence} onChange={(e) => setF({ ...f, user_confidence: e.target.value })} /></Field>
            <Field label="Target ₹"><input type="number" className={inputCls} value={f.target_price} onChange={(e) => setF({ ...f, target_price: e.target.value })} /></Field>
            <Field label="Stop ₹"><input type="number" className={inputCls} value={f.stop_price} onChange={(e) => setF({ ...f, stop_price: e.target.value })} /></Field>
          </div>
        )}
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={run} busy={busy} disabled={!idea.trim() && !f.symbol}>Check it</Button>
          <span className="text-xs text-slate-500">Saved to My ideas and tracked automatically.</span>
        </div>
      </Card>
      <div className="mt-4"><ErrorBox message={err} /></div>
      {busy && <Loading label="Running checks, simulations and the stress test…" />}
      {report && (
        <div className="mt-4 space-y-3">
          {report.thesis_id && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-200">
              Saved. Parakh will mark it hit, stopped or timed out on its own and write an autopsy.{" "}
              <Link href={`/ideas/${report.thesis_id}`} className="underline underline-offset-2">Open this idea →</Link>
            </div>
          )}
          <ThesisReport r={report} />
        </div>
      )}
    </div>
  );
}
