"use client";
import { ReactNode } from "react";

/**
 * Consistent card wrapper for every research panel. 44px minimum height on
 * interactive children is enforced by the components that use it.
 */
export default function SectionCard({
  title, subtitle, badge, children, className = "", actions,
}: {
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}) {
  return (
    <section className={`glass rounded-2xl p-5 ${className}`}>
      <header className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-slate-200">
            {title}
          </h2>
          {subtitle ? (
            <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {badge}
          {actions}
        </div>
      </header>
      {children}
    </section>
  );
}
