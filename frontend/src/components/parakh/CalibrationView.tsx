"use client";
import Link from "next/link";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ComposedChart, Tooltip, XAxis, YAxis, ReferenceLine } from "recharts";
import { Card, Empty, PageHeader, Stat } from "./ui";

/** The confidence-vs-results report. Used by the signed-in page and the public sample. */
export default function CalibrationView({ c, checkHref = "/check" }: { c: any; checkHref?: string }) {
  const points = (c.bins || []).filter((b: any) => b.n > 0).map((b: any) => ({ stated: Math.round(b.stated * 100), actual: Math.round(b.actual * 100), n: b.n }));
  return (
    <div className="space-y-4">
      <PageHeader title="Calibration" subtitle="When you say you're 80% sure, are you right 80% of the time? This is the skill that separates traders who last from those who don't." />
      {c.status !== "ok" ? (
        <Empty>
          {c.message} <Link href={checkHref} className="underline">Check more ideas</Link> — they resolve automatically against real prices.
        </Empty>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Stat label="Calibration score" value={`${c.score}/100`} hint="100 = perfect, 75 ≈ always saying 50%" tone={c.score >= 80 ? "good" : c.score < 70 ? "bad" : "neutral"} />
            <Stat label="Avg stated confidence" value={`${Math.round(c.avg_confidence * 100)}%`} />
            <Stat label="Actual hit rate" value={`${Math.round(c.hit_rate * 100)}%`} />
            <Stat label="Brier score" value={c.brier} hint={c.reference_brier != null ? `base rate on same ideas: ${c.reference_brier}` : "lower is better"} />
          </div>
          <Card>{c.band_line && <p className="mb-1 text-lg font-semibold text-white">{c.band_line}</p>}<p className="text-base text-slate-100">{c.verdict}</p>{c.reference_note && <p className="mt-1 text-xs text-slate-500">{c.reference_note}</p>}</Card>
        </>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Stated vs actual (dots on the line = perfectly calibrated)">
          <div className="h-64">
            <ResponsiveContainer>
              <ComposedChart margin={{ top: 8, right: 8, bottom: 8, left: -12 }}>
                <CartesianGrid stroke="#1e293b" />
                <XAxis type="number" dataKey="stated" domain={[50, 100]} unit="%" stroke="#64748b" fontSize={11} name="You said" />
                <YAxis type="number" dataKey="actual" domain={[0, 100]} unit="%" stroke="#64748b" fontSize={11} name="Came true" />
                <ReferenceLine segment={[{ x: 50, y: 50 }, { x: 100, y: 100 }]} stroke="#475569" strokeDasharray="4 4" />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                <Scatter data={points} fill="#34d399" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="By confidence band">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase text-slate-500"><tr><th className="py-1">You said</th><th>Ideas</th><th>Came true</th></tr></thead>
            <tbody className="divide-y divide-slate-800/70">
              {(c.bins || []).map((b: any) => (
                <tr key={b.range}><td className="py-1.5">{b.range}</td><td>{b.n}</td>
                  <td className={b.actual == null ? "text-slate-500" : b.actual + 0.1 < b.stated ? "text-rose-300" : "text-emerald-300"}>
                    {b.actual == null ? "—" : `${Math.round(b.actual * 100)}%`}</td></tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
      {c.trend?.length > 1 && (
        <Card title={`Score over time (rolling ${c.floor} ideas)`}>
          <div className="h-56">
            <ResponsiveContainer>
              <LineChart data={c.trend} margin={{ top: 8, right: 8, bottom: 8, left: -12 }}>
                <CartesianGrid stroke="#1e293b" /><XAxis dataKey="date" stroke="#64748b" fontSize={11} /><YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} />
                <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }} />
                <Line dataKey="score" stroke="#34d399" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}
    </div>
  );
}
