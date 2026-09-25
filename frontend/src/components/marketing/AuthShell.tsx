"use client";
import { type ReactNode } from "react";
import Link from "next/link";
import { Wordmark } from "./Logo";

/** Shared auth shell: one card, one column, no competing hero gesture. */
export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="relative min-h-[80vh] px-6 py-28">
      <div className="mx-auto w-full max-w-md">
        <Link href="/" className="inline-flex min-h-11 items-center" aria-label="QuantPulse AI home">
          <Wordmark className="text-[15px]" />
        </Link>
        <div className="mk-card mt-6 px-7 py-8">
          <h1 className="text-2xl font-semibold tracking-[-0.02em]">{title}</h1>
          <p className="mt-2 text-sm text-fg-muted">{subtitle}</p>
          <div className="mt-7">{children}</div>
        </div>
        <div className="mt-6 text-center text-sm text-fg-muted">{footer}</div>
      </div>
    </div>
  );
}

/** Submit button: pure presentational, honest disabled + aria-busy. */
export function SubmitButton({
  busy,
  busyLabel,
  children,
}: {
  busy: boolean;
  busyLabel: string;
  children: ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={busy}
      aria-busy={busy}
      aria-disabled={busy}
      className="mk-btn mk-btn-primary w-full aria-disabled:opacity-60"
    >
      {busy ? busyLabel : children}
    </button>
  );
}
