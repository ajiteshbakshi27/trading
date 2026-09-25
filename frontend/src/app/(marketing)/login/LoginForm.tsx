"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import AuthShell, { SubmitButton } from "@/components/marketing/AuthShell";
import { Input, PasswordInput, ErrorSummary } from "@/components/marketing/Form";
import { issueSession } from "@/lib/auth";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export default function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const summaryRef = useRef<HTMLDivElement>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const found: Record<string, string> = {};
    if (!email) found.email = "Enter your email address";
    else if (!EMAIL_RE.test(email)) found.email = "That email address is not valid";
    if (!password) found.password = "Enter your password";
    setErrors(found);
    if (Object.keys(found).length) {
      // Move focus to the summary so keyboard + screen-reader users land on it.
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    setBusy(true);
    await new Promise((r) => setTimeout(r, 700));
    issueSession(email, email.split("@")[0]);
    // `next` stays the route param: never shadow it with the error map above.
    router.push(next.startsWith("/") ? next : "/dashboard");
  };

  return (
    <AuthShell
      title="Sign in"
      subtitle="Pick up where the tape left off."
      footer={
        <>
          No account?{" "}
          <Link href="/signup" className="text-fg underline underline-offset-4">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <ErrorSummary ref={summaryRef} errors={errors} />
        <Input
          id="email"
          name="email"
          type="email"
          inputMode="email"
          label="Email"
          autoComplete="email"
          onChange={setEmail}
          error={errors.email}
        />
        <PasswordInput
          id="password"
          name="password"
          label="Password"
          autoComplete="current-password"
          onChange={setPassword}
          error={errors.password}
        />
        <Link
          href="/forgot-password"
          className="inline-flex min-h-11 items-center text-sm text-fg-muted underline underline-offset-4 hover:text-fg"
        >
          Forgot password?
        </Link>
        <SubmitButton busy={busy} busyLabel="Signing in…">
          Sign in
        </SubmitButton>
        <p className="text-center text-xs text-fg-muted">
          Demo authentication — the session is a fake JWT in localStorage. No account, no email, no
          server.
        </p>
      </form>
    </AuthShell>
  );
}
