"use client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

export default function OrderBookDepth({ book }: { book: any }) {
  if (!book) return <p className="text-sm text-slate-500">No book data.</p>;
  const bids = (book.bids || []).map((b: any) => ({ price: b.price, size: -b.size }));
  const asks = (book.asks || []).map((a: any) => ({ price: a.price, size: a.size }));
  const data = [...bids.reverse(), ...asks];
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 40 }}>
          <XAxis type="number" tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <YAxis type="category" dataKey="price" tick={{ fill: "#94a3b8", fontSize: 11 }} width={55} />
          <Tooltip
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
            formatter={(v: any) => Math.abs(Number(v)).toLocaleString()}
            labelFormatter={(l: any) => `@ $${l}`}
            contentStyle={{ background: "#0f172a", border: "1px solid #334155" }} />
          <Bar dataKey="size">
            {data.map((d: any, i: number) => (
              <Cell key={i} fill={d.size < 0 ? "#22c55e" : "#ef4444"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
