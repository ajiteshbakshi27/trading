/** Static product frame used in the hero — representative of the live terminal. */
const SIGNALS = [
  { sym: "NVDA", type: "BET FOR", dir: "LONG", px: "228.87", conf: 82, dirClass: "text-emerald-400", chip: "bg-emerald-500/10 border-emerald-500/30" },
  { sym: "TSLA", type: "BET AGAINST", dir: "SHORT", px: "378.90", conf: 91, dirClass: "text-rose-400", chip: "bg-rose-500/10 border-rose-500/30" },
  { sym: "AAPL", type: "BET FOR", dir: "LONG", px: "339.75", conf: 74, dirClass: "text-emerald-400", chip: "bg-emerald-500/10 border-emerald-500/30" },
];

const BARS = [0.62, 0.38, 0.71, 0.55, 0.84, 0.47, 0.66, 0.91, 0.58, 0.73];

export default function TerminalFrame() {
  return (
    <div className="mk-card overflow-hidden shadow-lg">
      {/* chrome */}
      <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-rose-500/70" />
          <span className="h-2 w-2 rounded-full bg-amber-400/70" />
          <span className="h-2 w-2 rounded-full bg-emerald-500/70" />
        </div>
        <span className="tnum text-[11px] text-fg-muted">quantpulse · live desk</span>
        <span className="flex items-center gap-1.5 text-[11px] text-emerald-400">
          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-500" /> streaming
        </span>
      </div>

      {/* body */}
      <div className="grid grid-cols-12 gap-3 p-4">
        <div className="col-span-7 space-y-2">
          {SIGNALS.map((s) => (
            <div key={s.sym} className="flex items-center justify-between rounded-xl border border-hairline bg-surface-2/60 px-3 py-2">
              <div className="flex items-center gap-2">
                <span className="tnum text-[13px] font-semibold">{s.sym}</span>
                <span className={`rounded border px-1.5 py-px text-[10px] font-semibold ${s.chip} ${s.dirClass}`}>{s.type}</span>
              </div>
              <div className="tnum text-[11px] text-fg-muted">
                ${s.px} · {s.conf}%
              </div>
            </div>
          ))}
        </div>

        <div className="col-span-5 rounded-xl border border-hairline bg-surface-2/60 p-3">
          <div className="mb-2 text-[10px] uppercase tracking-[0.14em] text-fg-muted">Order flow</div>
          <div className="flex h-20 items-end gap-1">
            {BARS.map((b, i) => (
              <span key={i} className="flex-1 rounded-t bg-accent/70" style={{ height: `${b * 100}%` }} />
            ))}
          </div>
          <div className="mt-2 text-[10px] text-fg-muted">OFI +0.62 · bullish</div>
        </div>
      </div>

      {/* footer strip */}
      <div className="grid grid-cols-3 border-t border-hairline text-center">
        {[["Quantum weights", "PennyLane QAOA"], ["Risk", "VaR 95% · CVaR"], ["Fades today", "3"]].map(([k, v]) => (
          <div key={k} className="border-r border-hairline px-2 py-3 last:border-r-0">
            <div className="text-[10px] uppercase tracking-[0.14em] text-fg-muted">{k}</div>
            <div className="tnum mt-0.5 text-[12px] font-semibold">{v}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
