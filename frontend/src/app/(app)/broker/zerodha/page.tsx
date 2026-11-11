"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { post } from "@/lib/api";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/parakh/ui";

function Callback() {
  const params = useSearchParams();
  const [state, setState] = useState<{ ok?: any; err?: string }>({});
  const once = useRef(false);
  useEffect(() => {
    if (once.current) return;
    once.current = true;
    const token = params.get("request_token");
    if (params.get("status") !== "success" || !token) {
      setState({ err: "Zerodha login was cancelled or failed." });
      return;
    }
    post("/api/parakh/broker/zerodha/callback", { request_token: token })
      .then((ok) => setState({ ok })).catch((e) => setState({ err: e.message }));
  }, [params]);
  if (state.err) return <ErrorBox message={state.err} />;
  if (!state.ok) return <Loading label="Connecting your Zerodha account…" />;
  return (
    <Card>
      <p className="text-sm text-emerald-300">Connected as {state.ok.broker_user_id}. Synced {state.ok.sync?.added ?? 0} new trades from today.</p>
      <p className="mt-2 text-xs text-slate-400">{state.ok.sync?.note}</p>
      <Link href="/journal" className="mt-3 inline-block text-sm underline">Go to your journal →</Link>
    </Card>
  );
}

export default function ZerodhaCallbackPage() {
  return (
    <div>
      <PageHeader title="Zerodha" />
      <Suspense fallback={<Loading />}><Callback /></Suspense>
    </div>
  );
}
