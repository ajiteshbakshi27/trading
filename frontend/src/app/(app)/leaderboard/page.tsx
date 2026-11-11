"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, Empty, ErrorBox, Loading, PageHeader } from "@/components/parakh/ui";

export default function LeaderboardPage() {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api("/api/parakh/leaderboard").then(setD).catch((e) => setErr(e.message)); }, []);
  return (
    <div className="space-y-4">
      <PageHeader title="Leaderboard" subtitle="Ranked by calibration — how honest traders are about their own odds — not by profit. Every idea is sealed when shared and resolved automatically." />
      <ErrorBox message={err} />
      {!d ? <Loading /> : d.leaderboard.length === 0 ? (
        <Empty>No one has {d.floor}+ resolved public ideas yet. Set a public handle in <Link href="/settings" className="underline">Settings</Link> and share ideas to get on the board.</Empty>
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase text-slate-500"><tr><th className="py-2">#</th><th>Trader</th><th>Ideas</th><th>Calibration</th><th>Hit rate</th><th>Avg confidence</th><th>Brier</th></tr></thead>
            <tbody className="divide-y divide-slate-800/70">
              {d.leaderboard.map((r: any) => (
                <tr key={r.handle}><td className="py-2">{r.rank}</td><td className="font-medium text-white">@{r.handle}</td><td>{r.n}</td><td>{r.calibration_score}</td>
                  <td>{Math.round(r.hit_rate * 100)}%</td><td>{Math.round(r.avg_confidence * 100)}%</td><td className="tabular-nums">{r.brier}</td></tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[11px] text-slate-500">{d.method}</p>
        </Card>
      )}
    </div>
  );
}
