"use client";
import { useMemo } from "react";
import {
  ComposedChart, Bar, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine,
} from "recharts";

/**
 * Hype vs Price — candlestick-style price line with Reddit mention volume
 * rendered as background bars. Lets the user see whether retail hype leads
 * or lags the price move.
 *
 * Data shape:
 *   price:  [{ time, close }]        — from /api/candles
 *   hype:   [{ time, mentions }]     — from /api/divergence or mock
 */
export default function HypeVsPrice({
  price,
  hype,
  symbol,
  currency = "USD",
}: {
  price: Array<{ time: number; close: number }>;
  hype: Array<{ time: number; mentions: number }>;
  symbol: string;
  currency?: string;
}) {
  const currSymbol = currency === "INR" ? "₹" : "$";
  const data = useMemo(() => {
    const hypeByTime = new Map(hype.map((h) => [h.time, h.mentions]));
    return price.map((p) => ({
      time: p.time,
      close: p.close,
      mentions: hypeByTime.get(p.time) ?? 0,
    }));
  }, [price, hype]);

  const maxMentions = Math.max(...data.map((d) => d.mentions), 1);
  const minPrice = Math.min(...data.map((d) => d.close), 0);
  const maxPrice = Math.max(...data.map((d) => d.close), 1);
  const avgPrice = data.reduce((s, d) => s + d.close, 0) / data.length || 0;

  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
          <XAxis
            dataKey="time"
            tickFormatter={(t) => new Date(t * 1000).toLocaleDateString()}
            tick={{ fill: "#64748b", fontSize: 10 }}
            axisLine={{ stroke: "#334155" }}
            tickLine={false}
          />
          <YAxis
            yAxisId="price"
            domain={[minPrice * 0.98, maxPrice * 1.02]}
            tick={{ fill: "#94a3b8", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={60}
          />
          <YAxis
            yAxisId="hype"
            orientation="right"
            domain={[0, maxMentions * 3]}
            tick={{ fill: "#f97316", fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "#0e1223",
              border: "1px solid #334155",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelFormatter={(t) => new Date(Number(t) * 1000).toLocaleDateString()}
            formatter={(value: any, name: string) => {
              if (name === "close") return [`${currSymbol}${Number(value).toFixed(2)}`, "Price"];
              if (name === "mentions") return [value, "Reddit Mentions"];
              return [value, name];
            }}
          />
          <ReferenceLine
            yAxisId="price"
            y={avgPrice}
            stroke="#475569"
            strokeDasharray="4 4"
          />
          <Bar
            yAxisId="hype"
            dataKey="mentions"
            fill="#f97316"
            opacity={0.25}
            radius={[2, 2, 0, 0]}
          />
          <Line
            yAxisId="price"
            dataKey="close"
            stroke="#60a5fa"
            strokeWidth={2}
            dot={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2 flex items-center justify-between text-[10px]">
        <span className="flex items-center gap-1.5 text-blue-300">
          <span className="inline-block h-0.5 w-4 bg-blue-400" /> Price ({symbol})
        </span>
        <span className="flex items-center gap-1.5 text-orange-300">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-orange-500/40" /> Reddit Hype
        </span>
      </div>
    </div>
  );
}
