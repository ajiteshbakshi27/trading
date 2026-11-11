"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthShell, { SubmitButton } from "@/components/marketing/AuthShell";
import { Input, PasswordInput, ErrorSummary } from "@/components/marketing/Form";
import { signUp } from "@/lib/auth";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function SignupPage() {
  const router = useRouter();
  const summaryRef = useRef<HTMLDivElement>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!email) found.email = "Enter your email address";
    else if (!EMAIL_RE.test(email)) found.email = "That email address is not valid";
    if (!password) found.password = "Choose a password";
    else if (password.length < 10) found.password = "Use at least 10 characters";
    setErrors(found);
    if (Object.keys(found).length) {
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    setBusy(true);
    try {
      const needsConfirm = await signUp(email, password, email.split("@")[0]);
      if (needsConfirm) { setConfirm(true); setBusy(false); return; }
    } catch (err: any) {
      setBusy(false);
      setErrors({ email: err?.message || "Sign-up failed" });
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    router.push("/home");
  };

  if (confirm) {
    return (
      <AuthShell title="Confirm your email" subtitle={`We sent a link to ${email}. Click it, then sign in.`}
        footer={<Link href="/login" className="text-fg underline underline-offset-4">Go to sign in</Link>}>
        <div role="status" className="rounded-xl border border-hairline bg-surface-2/60 p-4 text-sm text-fg-muted">
          Didn&apos;t get it? Check spam, or try signing up again in a minute.
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="Free. No card. Connect your broker later if you want."
      footer={
        <>
          Already have one?{" "}
          <Link href="/login" className="text-fg underline underline-offset-4">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary ref={summaryRef} errors={errors} title="Check these fields" />
        <Input
          id="email"
          name="email"
          type="email"
          inputMode="email"
          label="Work email"
          autoComplete="email"
          onChange={setEmail}
          error={errors.email}
        />
        <PasswordInput
          id="password"
          name="password"
          label="Password"
          autoComplete="new-password"
          hint="10 characters minimum. A passphrase beats a symbol soup."
          onChange={setPassword}
          error={errors.password}
        />
        <label className="flex items-start gap-3 text-sm text-fg-muted">
          <input
            type="checkbox"
            name="risk"
            required
            className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--color-accent)]"
          />
          <span>
            I understand this is a demo terminal and nothing here is investment advice.
          </span>
        </label>
        <SubmitButton busy={busy} busyLabel="Creating account…">
          Create account
        </SubmitButton>
      </form>
    </AuthShell>
  );
}
