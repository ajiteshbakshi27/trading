"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, post } from "@/lib/api";
import ThesisReport from "@/components/parakh/ThesisReport";
import Autopsy from "@/components/parakh/Autopsy";
import { Button, Card, ErrorBox, Loading, OutcomePill, PageHeader, inr, signedPct } from "@/components/parakh/ui";

export default function IdeaDetail() {
  const { id } = useParams<{ id: string }>();
  const [row, setRow] = useState<any>(null);
  const [err, setErr] = useState("");
  const [share, setShare] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api(`/api/parakh/theses/${id}`).then(setRow).catch((e) => setErr(e.message)); }, [id]);

  const publish = async () => {
    setBusy(true);
    try {
      const s = await post<any>(`/api/parakh/theses/${id}/publish`, {});
      const url = `${window.location.origin}/t/${s.slug}`;
      setShare({ ...s, url });
      try { await navigator.clipboard.writeText(url); } catch { /* ignore */ }
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  if (err) return <ErrorBox message={err} />;
  if (!row) return <Loading />;
  return (
    <div className="space-y-4">
      <PageHeader title={`${row.symbol} — ${row.direction === "LONG" ? "expects rise" : "expects fall"}`}
        subtitle={<>&ldquo;{row.idea_text}&rdquo; · checked {new Date(row.created_at).toLocaleString("en-IN")}</>}
        action={<Link href="/ideas" className="text-sm text-slate-400 underline">← All ideas</Link>} />
      <Card>
        <div className="flex flex-wrap items-center gap-4">
          <OutcomePill status={row.status} />
          {row.status !== "open" && (
            <span className="text-sm text-slate-300">Exit {inr(row.exit_price)} · <span className={(row.outcome_return_pct ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"}>{signedPct(row.outcome_return_pct)}</span></span>
          )}
          <div className="ml-auto flex items-center gap-2">
            {row.is_public || share ? (
              <span className="text-xs text-slate-400">Public link: <a className="underline" href={share?.url || `/t/${row.share_slug}`}>{share?.url || `/t/${row.share_slug}`}</a></span>
            ) : (
              <Button tone="ghost" onClick={publish} busy={busy}>Share publicly (sealed)</Button>
            )}
          </div>
        </div>
        {share && <p className="mt-2 text-[11px] text-slate-500">Link copied. Seal: <code className="break-all">{share.seal}</code></p>}
      </Card>
      {row.autopsy && <Autopsy a={row.autopsy} />}
      {row.report && <ThesisReport r={row.report} />}
    </div>
  );
}
