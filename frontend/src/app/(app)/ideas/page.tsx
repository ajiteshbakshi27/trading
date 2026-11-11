"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button, Card, Empty, ErrorBox, Loading, OutcomePill, PageHeader, inr, signedPct } from "@/components/parakh/ui";

const TABS = ["all", "open", "hit", "miss", "expired"];

export default function IdeasPage() {
  const [rows, setRows] = useState<any[] | null>(null);
  const [tab, setTab] = useState("all");
  const [err, setErr] = useState("");

  useEffect(() => {
    setRows(null);
    api<any>(`/api/parakh/theses${tab === "all" ? "" : `?status=${tab}`}`)
      .then((j) => setRows(j.theses)).catch((e) => { setErr(e.message); setRows([]); });
  }, [tab]);

  return (
    <div>
      <PageHeader title="My ideas" subtitle="Every idea you check is tracked against real prices and resolved automatically — no editing after the fact."
        action={<Link href="/check"><Button>Check a new idea</Button></Link>} />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-full px-3 py-1 text-xs capitalize ${tab === t ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>{t}</button>
        ))}
      </div>
      <ErrorBox message={err} />
      {rows === null ? <Loading /> : rows.length === 0 ? (
        <Empty>No ideas here yet. <Link href="/check" className="underline">Check your first trade idea</Link>.</Empty>
      ) : (
        <Card className="overflow-x-auto p-0 sm:p-0">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-[11px] uppercase tracking-wide text-slate-500">
              <tr><th className="p-3">Idea</th><th>Direction</th><th>Entry</th><th>Target / Stop</th><th>Confidence</th><th>Status</th><th className="pr-3 text-right">Result</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-800/70">
              {rows.map((r) => (
                <tr key={r.id} className="hover:bg-white/[0.02]">
                  <td className="p-3"><Link href={`/ideas/${r.id}`} className="font-medium text-white hover:underline">{r.symbol}</Link>
                    <div className="max-w-[18rem] truncate text-xs text-slate-500">{r.idea_text}</div></td>
                  <td className={r.direction === "LONG" ? "text-emerald-300" : "text-rose-300"}>{r.direction === "LONG" ? "Rise" : "Fall"}</td>
                  <td className="tabular-nums">{inr(r.entry_price)}</td>
                  <td className="tabular-nums text-xs">{inr(r.target_price)} / {inr(r.stop_price)}</td>
                  <td className="tabular-nums">{Math.round(r.user_confidence * 100)}%</td>
                  <td><OutcomePill status={r.status} /></td>
                  <td className={`pr-3 text-right tabular-nums ${(r.outcome_return_pct ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{signedPct(r.outcome_return_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
