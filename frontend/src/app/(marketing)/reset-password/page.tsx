"use client";
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell, { SubmitButton } from "@/components/marketing/AuthShell";
import { PasswordInput, ErrorSummary } from "@/components/marketing/Form";
import { updatePassword } from "@/lib/auth";

export default function ResetPasswordPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 10) { setError("Use at least 10 characters"); return; }
    setBusy(true);
    try {
      await updatePassword(password);
      router.push("/home");
    } catch (err: any) {
      setError(err?.message || "Couldn't update the password — the link may have expired.");
      setBusy(false);
    }
  };

  return (
    <AuthShell title="Set a new password" subtitle="Choose something you haven't used before."
      footer={<Link href="/login" className="text-fg underline underline-offset-4">Back to sign in</Link>}>
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={error ? { password: error } : {}} />
        <PasswordInput id="password" name="password" label="New password" autoComplete="new-password"
          onChange={setPassword} error={error || undefined} />
        <SubmitButton busy={busy} busyLabel="Saving…">Save password</SubmitButton>
      </form>
    </AuthShell>
  );
}
