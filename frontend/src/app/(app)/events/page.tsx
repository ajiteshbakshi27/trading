"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, DataModeTag, ErrorBox, Loading, PageHeader, signedPct } from "@/components/parakh/ui";

export default function EventsPage() {
  const [events, setEvents] = useState<any[]>([]);
  const [sel, setSel] = useState("UNION_BUDGET");
  const [map, setMap] = useState<any>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<any>("/api/parakh/events").then((j) => setEvents(j.events)).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { setMap(null); api(`/api/parakh/events/${sel}`).then(setMap).catch((e) => setErr(e.message)); }, [sel]);

  return (
    <div className="space-y-4">
      <PageHeader title="Event impact maps" subtitle="Which Indian stocks an event tends to touch, and — where past dates exist — how they actually moved." />
      <div className="flex flex-wrap gap-1.5">
        {events.map((e) => (
          <button key={e.id} onClick={() => setSel(e.id)}
            className={`rounded-full px-3 py-1 text-xs ${sel === e.id ? "bg-emerald-500 text-black" : "bg-white/5 text-slate-300 hover:bg-white/10"}`}>{e.name}</button>
        ))}
      </div>
      <ErrorBox message={err} />
      {!map ? <Loading /> : (
        <>
          <Card><div className="flex items-center justify-between"><div><h2 className="text-lg font-semibold text-white">{map.name}</h2><p className="text-xs text-slate-400">{map.when}</p></div>{map.data_mode !== "n/a" && <DataModeTag mode={map.data_mode} />}</div></Card>
          <div className="grid gap-4 lg:grid-cols-2">
            {map.themes.map((t: any) => (
              <Card key={t.theme} title={t.theme}>
                <p className="text-sm text-slate-300">{t.sensitivity}</p>
                {t.assets.length > 0 && (
                  <table className="mt-3 w-full text-sm">
                    <thead className="text-left text-[11px] uppercase text-slate-500"><tr><th className="py-1">Stock</th><th>Link</th><th className="text-right">Avg move</th><th className="text-right">Up</th></tr></thead>
                    <tbody className="divide-y divide-slate-800/70">
                      {t.assets.map((a: any) => (
                        <tr key={a.symbol}><td className="py-1.5">{a.symbol}<span className="ml-1 text-xs text-slate-500">{a.name}</span></td>
                          <td className="text-xs text-slate-400">{a.relation}{a.n != null ? ` (n=${a.n})` : ""}</td>
                          <td className={`text-right tabular-nums ${a.avg_move_pct == null ? "text-slate-500" : a.avg_move_pct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>{a.avg_move_pct == null ? "—" : signedPct(a.avg_move_pct)}</td>
                          <td className="text-right tabular-nums text-slate-400">{a.up_share == null ? "—" : `${Math.round(a.up_share * 100)}%`}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card>
            ))}
          </div>
          <p className="text-[11px] text-slate-500">{map.method}</p>
        </>
      )}
    </div>
  );
}
