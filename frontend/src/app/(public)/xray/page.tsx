"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { api, API } from "@/lib/api";
import XrayReport from "@/components/parakh/XrayReport";
import { Button, Card, ErrorBox, Loading, PageHeader } from "@/components/parakh/ui";

export default function PublicXrayPage() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const run = async (kind: "sample" | "file", file?: File) => {
    setBusy(kind); setErr(""); setData(null);
    try {
      if (kind === "sample") {
        setData(await api("/api/parakh/public/xray?sample=1", { method: "POST" }));
      } else if (file) {
        const fd = new FormData();
        fd.append("file", file);
        setData(await api("/api/parakh/public/xray", { method: "POST", body: fd }));
      }
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(""); if (fileRef.current) fileRef.current.value = ""; }
  };

  return (
    <div className="space-y-4">
      <PageHeader title="Tradebook X-ray"
        subtitle="Upload your tradebook and see, in rupees, which habits your losses come from. No sign-up. Your file is read once and not stored." />
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden"
            onChange={(e) => e.target.files?.[0] && run("file", e.target.files[0])} />
          <Button onClick={() => fileRef.current?.click()} busy={busy === "file"}>Upload tradebook CSV</Button>
          <Button tone="ghost" onClick={() => run("sample")} busy={busy === "sample"}>Use a sample tradebook</Button>
          <a href={`${API}/api/parakh/public/sample-tradebook.csv`} className="text-xs text-slate-400 underline underline-offset-2">Download the sample file</a>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          Zerodha: Console → Reports → Tradebook → choose segment and dates → download CSV. Other brokers: any CSV with
          symbol, buy/sell, quantity, price and date-time columns.
        </p>
      </Card>
      <ErrorBox message={err} />
      {busy && <Loading label="Pairing your buys and sells and looking for habits…" />}
      {data && (
        <>
          <XrayReport data={data} />
          <Card>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="max-w-xl text-sm text-slate-300">
                Sign up to keep your journal, check trade ideas before you place them, and see whether your confidence matches your results.
              </p>
              <div className="flex gap-2">
                <Link href="/try" className="rounded-lg bg-white/5 px-4 py-2 text-sm font-semibold text-slate-200 ring-1 ring-white/10 hover:bg-white/10">Check a trade idea</Link>
                <Link href="/signup" className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-black hover:bg-emerald-400">Sign up free</Link>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
