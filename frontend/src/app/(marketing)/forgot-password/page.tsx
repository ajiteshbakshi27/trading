"use client";
import { useState } from "react";
import Link from "next/link";
import AuthShell, { SubmitButton } from "@/components/marketing/AuthShell";
import { Input, ErrorSummary } from "@/components/marketing/Form";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !EMAIL_RE.test(email)) {
      setError("Enter the email address you signed up with");
      return;
    }
    setError("");
    setBusy(true);
    await new Promise((r) => setTimeout(r, 700));
    setBusy(false);
    setSent(true);
  };

  if (sent) {
    return (
      <AuthShell
        title="Check your email"
        subtitle={`If ${email} has an account, a reset link is on its way.`}
        footer={
          <Link href="/login" className="text-fg underline underline-offset-4">
            Back to sign in
          </Link>
        }
      >
        <div role="status" className="rounded-xl border border-hairline bg-surface-2/60 p-4 text-sm text-fg-muted">
          This demo does not send email. The success state exists so you can see how it behaves.
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Reset password"
      subtitle="We will email you a link to set a new one."
      footer={
        <Link href="/login" className="text-fg underline underline-offset-4">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary errors={error ? { email: error } : {}} />
        <Input
          id="email"
          name="email"
          type="email"
          inputMode="email"
          label="Email"
          autoComplete="email"
          onChange={setEmail}
          error={error}
        />
        <SubmitButton busy={busy} busyLabel="Sending…">
          Send reset link
        </SubmitButton>
      </form>
    </AuthShell>
  );
}
