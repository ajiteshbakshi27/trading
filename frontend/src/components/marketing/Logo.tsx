export function Logo({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className} aria-hidden="true">
      <path d="M2 15.5 6.5 9l4 3.5L16 4.5" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.5 4.5H16V7" stroke="var(--color-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M2 20h20" stroke="var(--color-hairline)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 font-semibold tracking-tight ${className}`}>
      <Logo />
      QuantPulse&nbsp;AI
    </span>
  );
}
