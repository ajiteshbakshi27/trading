"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, post } from "@/lib/api";
import { Button, Card, ErrorBox, Field, Loading, PageHeader, inputCls } from "@/components/parakh/ui";

export default function SettingsPage() {
  const [s, setS] = useState<any>(null);
  const [me, setMe] = useState<any>(null);
  const [err, setErr] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/parakh/settings").then(setS).catch((e) => setErr(e.message));
    api("/api/parakh/me").then(setMe).catch(() => {});
  }, []);

  const save = async () => {
    setBusy(true); setErr(""); setOk("");
    try {
      const body: any = { display_name: s.display_name || undefined, hype_alerts: s.hype_alerts, hype_threshold: Number(s.hype_threshold) };
      if (s.public_handle) body.public_handle = s.public_handle;
      if (s.telegram_chat_id) body.telegram_chat_id = s.telegram_chat_id;
      setS({ ...s, ...(await post("/api/parakh/settings", body, "PUT")) });
      setOk("Saved.");
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const [confirmText, setConfirmText] = useState("");
  const [delBusy, setDelBusy] = useState(false);
  const download = async () => {
    setErr("");
    try {
      const data = await api("/api/parakh/account/export");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url; a.download = "parakh-my-data.json"; a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { setErr(e.message); }
  };
  const deleteAll = async () => {
    setDelBusy(true); setErr(""); setOk("");
    try {
      const r = await api<any>("/api/parakh/account/data?confirm=DELETE", { method: "DELETE" });
      const n = Object.values(r.deleted as Record<string, number>).reduce((a, b) => a + b, 0);
      setConfirmText("");
      setS({ ...(await api("/api/parakh/settings")) });
      setOk(`Deleted. ${n} record${n === 1 ? "" : "s"} removed.`);
    } catch (e: any) { setErr(e.message); } finally { setDelBusy(false); }
  };
  const disconnect = async () => { await api("/api/parakh/broker/zerodha", { method: "DELETE" }); setS({ ...s, zerodha: { connected: false } }); };
  const connect = async () => { try { window.location.href = (await api<any>("/api/parakh/broker/zerodha/login-url")).url; } catch (e: any) { setErr(e.message); } };

  if (!s) return err ? <ErrorBox message={err} /> : <Loading />;
  return (
    <div className="max-w-2xl space-y-4">
      <PageHeader title="Settings" />
      <ErrorBox message={err} />
      <Card title="Profile">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Display name"><input className={inputCls} value={s.display_name || ""} onChange={(e) => setS({ ...s, display_name: e.target.value })} /></Field>
          <Field label="Public handle" hint="3–20 lowercase letters, numbers, _ · shown on shared ideas and the leaderboard">
            <input className={inputCls} value={s.public_handle || ""} onChange={(e) => setS({ ...s, public_handle: e.target.value.toLowerCase() })} placeholder="e.g. nifty_ninja" />
          </Field>
        </div>
      </Card>
      <Card title="Telegram alerts">
        <ol className="mb-3 list-decimal space-y-1 pl-4 text-xs text-slate-400">
          <li>Open Telegram and start a chat with the Parakh bot{me?.features?.telegram ? "" : " (the server admin must set TELEGRAM_BOT_TOKEN first)"}.</li>
          <li>Message <code>@userinfobot</code> to get your numeric chat ID, and paste it below.</li>
        </ol>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Chat ID"><input className={inputCls} value={s.telegram_chat_id || ""} onChange={(e) => setS({ ...s, telegram_chat_id: e.target.value.trim() })} /></Field>
          <Field label="Alert sensitivity" hint="lower = more alerts"><input type="number" min={0.5} max={6} step={0.5} className={inputCls} value={s.hype_threshold} onChange={(e) => setS({ ...s, hype_threshold: e.target.value })} /></Field>
          <label className="flex items-end gap-2 pb-2 text-sm text-slate-300"><input type="checkbox" checked={!!s.hype_alerts} onChange={(e) => setS({ ...s, hype_alerts: e.target.checked })} /> Hype radar alerts</label>
        </div>
      </Card>
      <div className="flex items-center gap-3"><Button onClick={save} busy={busy}>Save settings</Button>{ok && <span className="text-sm text-emerald-300">{ok}</span>}</div>
      <Card title="Zerodha">
        {s.zerodha?.connected ? (
          <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
            Connected as <b>{s.zerodha.broker_user_id}</b>{s.zerodha.last_sync_at && <span className="text-xs text-slate-500">· last sync {new Date(s.zerodha.last_sync_at).toLocaleString("en-IN")}</span>}
            <Button tone="ghost" onClick={() => post("/api/parakh/broker/zerodha/sync", {}).then(() => setOk("Synced.")).catch((e) => setErr(e.message))}>Sync now</Button>
            <Button tone="ghost" onClick={disconnect}>Disconnect</Button>
          </div>
        ) : (
          <div className="flex items-center gap-3 text-sm text-slate-400">
            Not connected. <Button tone="ghost" onClick={connect}>Connect Zerodha</Button>
          </div>
        )}
        <p className="mt-2 text-[11px] text-slate-500">Read-only: Parakh reads your executed trades and never places orders. Zerodha sessions expire each morning.</p>
      </Card>
      <Card title="Your data">
        <p className="text-sm text-slate-300">Everything Parakh stores about you: ideas, trades, rules, settings and alerts.</p>
        <div className="mt-3"><Button tone="ghost" onClick={download}>Download my data</Button></div>
        <div className="mt-5 rounded-xl border border-rose-500/30 bg-rose-500/5 p-3">
          <div className="text-sm font-semibold text-rose-200">Delete all my data</div>
          <p className="mt-1 text-xs text-slate-400">
            Removes your ideas, journal trades, rules, settings, alerts and broker connection, now. This cannot be undone.
            Your login stays, so you can keep using Parakh from a clean start.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <input className={inputCls + " w-44"} value={confirmText} onChange={(e) => setConfirmText(e.target.value)}
              placeholder="Type DELETE" aria-label="Type DELETE to confirm" />
            <Button tone="danger" onClick={deleteAll} busy={delBusy} disabled={confirmText !== "DELETE"}>Delete everything</Button>
          </div>
        </div>
        <p className="mt-3 text-[11px] text-slate-500">
          Read what is stored and who else sees it on the <Link href="/legal#privacy" className="underline underline-offset-2">privacy page</Link>.
        </p>
      </Card>
      {me && (
        <Card title="Server features">
          <ul className="grid grid-cols-2 gap-1 text-xs text-slate-400">
            {Object.entries(me.features).map(([k, v]: any) => <li key={k}>{k}: <span className={v === true || v === "redis" ? "text-emerald-300" : "text-slate-500"}>{String(v)}</span></li>)}
            <li>auth: <span className="text-slate-300">{me.auth_mode}</span></li>
          </ul>
        </Card>
      )}
    </div>
  );
}
