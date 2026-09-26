"use client";
import DataModeBadge from "./DataModeBadge";
import { LAYER_META } from "@/lib/research";
import { ACCENT_TEXT } from "./EvidenceBar";

/**
 * Detail panel for one node in the propagation chain: raw signal, source,
 * contribution, freshness and historical context.
 */
export default function NodeDetail({
  node,
}: {
  node: {
    layer: string;
    status: string;
    label: string;
    raw_signal: string;
    timestamp: string;
    lag_s: number;
    source_label: string;
    contribution: number;
    freshness: string;
    freshness_s: number;
    confidence: number;
    direction: string;
    data_mode: string;
    relation: string;
    raw: Record<string, unknown>;
    historical_context: {
      status: string;
      label: string;
      note: string;
    };
  } | null;
}) {
  if (!node) {
    return (
      <p className="rounded-xl border border-dashed border-slate-700 p-6 text-center text-sm text-slate-500">
        Select a node in the chain to inspect its raw signal, source and
        contribution.
      </p>
    );
  }
  const meta = LAYER_META[node.layer] ?? { label: node.layer, accent: "uncertainty" };
  return (
    <div className="rounded-xl border border-slate-700/60 bg-white/[0.03] p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-semibold ${ACCENT_TEXT[meta.accent]}`}>
            {meta.label}
          </span>
          <span className="text-xs text-slate-500">· {node.status}</span>
        </div>
        <DataModeBadge mode={node.data_mode} />
      </div>
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Raw signal</dt>
          <dd className="mt-0.5 font-medium text-slate-200">{node.raw_signal}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Source</dt>
          <dd className="mt-0.5 font-medium text-slate-200">{node.source_label}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Timestamp</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-slate-200">
            {node.timestamp}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Lag</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-slate-200">
            {node.lag_s}s after event
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Contribution</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-slate-200">
            {(node.contribution * 100).toFixed(1)}%
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Freshness</dt>
          <dd className="mt-0.5 font-medium text-slate-200">
            {node.freshness} ({node.freshness_s}s)
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Confidence</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-slate-200">
            {(node.confidence * 100).toFixed(1)}%
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Direction</dt>
          <dd className="mt-0.5 font-medium text-slate-200">{node.direction}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Relation</dt>
          <dd className="mt-0.5 font-medium text-slate-200">{node.relation}</dd>
        </div>
      </dl>
      {node.raw && Object.keys(node.raw).length > 0 ? (
        <div className="mt-3">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Raw observation
          </h4>
          <pre className="max-h-40 overflow-auto rounded-lg bg-black/40 p-3 text-[11px] leading-relaxed text-slate-300">
            {JSON.stringify(node.raw, null, 2)}
          </pre>
        </div>
      ) : null}
      <div className="mt-3 rounded-lg border border-slate-700/50 bg-black/20 p-3">
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Historical context
        </h4>
        <p className="text-xs text-slate-400">{node.historical_context.note}</p>
        {node.historical_context.status === "insufficient_data" ? (
          <p className="mt-1 text-[10px] font-semibold text-rose-300">
            {node.historical_context.label}
          </p>
        ) : null}
      </div>
    </div>
  );
}
