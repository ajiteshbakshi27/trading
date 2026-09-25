"use client";
import { useId, useState, forwardRef, type ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ *
 * Form primitives — token-only, 44px targets, focus + error wired.
 * a11y rules honoured: label association, aria-invalid, aria-describedby,
 * role=alert on errors, paste allowed (no onpaste handlers anywhere).
 * ------------------------------------------------------------------ */

export function Field({
  label,
  error,
  hint,
  children,
  htmlFor,
}: {
  label: string;
  error?: string;
  hint?: string;
  children: ReactNode;
  htmlFor: string;
}) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-fg">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${htmlFor}-hint`} className="text-xs text-fg-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

const base =
  "mk-input flex min-h-11 w-full items-center gap-2 rounded-xl border bg-surface-2/60 px-3 text-sm text-fg transition-colors duration-fast placeholder:text-fg-muted/70 focus:outline-none";

export function Input({
  id: idProp,
  label,
  error,
  hint,
  type = "text",
  autoComplete,
  inputMode,
  name,
  defaultValue,
  required,
  onChange,
}: {
  id?: string;
  label: string;
  error?: string;
  hint?: string;
  type?: string;
  autoComplete?: string;
  inputMode?: "email" | "text" | "numeric";
  name: string;
  defaultValue?: string;
  required?: boolean;
  onChange?: (v: string) => void;
}) {
  const auto = useId();
  const id = idProp || auto;
  return (
    <Field label={label} error={error} hint={hint} htmlFor={id}>
      <input
        id={id}
        name={name}
        type={type}
        inputMode={inputMode}
        autoComplete={autoComplete}
        required={required}
        defaultValue={defaultValue}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
        onChange={(e) => onChange?.(e.target.value)}
        className={cn(base, error ? "border-destructive" : "border-hairline focus:border-accent")}
      />
    </Field>
  );
}

export function PasswordInput({
  id: idProp,
  label,
  error,
  hint,
  autoComplete = "current-password",
  name,
  required,
  onChange,
}: {
  id?: string;
  label: string;
  error?: string;
  hint?: string;
  autoComplete?: string;
  name: string;
  required?: boolean;
  onChange?: (v: string) => void;
}) {
  const auto = useId();
  const id = idProp || auto;
  const [show, setShow] = useState(false);
  return (
    <Field label={label} error={error} hint={hint} htmlFor={id}>
      <div className={cn(base, error ? "border-destructive" : "border-hairline focus-within:border-accent")}>
        <input
          id={id}
          name={name}
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
          onChange={(e) => onChange?.(e.target.value)}
          className="min-h-11 w-full bg-transparent text-sm text-fg placeholder:text-fg-muted/70 focus:outline-none"
        />
        <button
          type="button"
          onClick={() => setShow((s) => !s)}
          aria-pressed={show}
          aria-label={show ? `Hide ${label}` : `Show ${label}`}
          className="inline-flex h-11 w-11 items-center justify-center text-fg-muted transition-colors duration-fast hover:text-fg"
        >
          {show ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
        </button>
      </div>
    </Field>
  );
}

export const ErrorSummary = forwardRef<
  HTMLDivElement,
  { title?: string; errors: Record<string, string> }
>(function ErrorSummary({ title = "There is a problem", errors }, ref) {
  const entries = Object.entries(errors);
  if (!entries.length) return null;
  return (
    <div
      ref={ref}
      role="alert"
      tabIndex={-1}
      className="rounded-xl border border-destructive/40 bg-destructive/10 p-4"
    >
      <p className="text-sm font-semibold text-destructive">{title}</p>
      <ul className="mt-2 space-y-1">
        {entries.map(([k, v]) => (
          <li key={k}>
            <a href={`#${k}`} className="text-sm text-fg underline underline-offset-2">
              {v}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
});
