"use client";
import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger, useGSAP);

const STATS = [
  { value: 9, suffix: "", label: "tickers streamed" },
  { value: 1, suffix: "s", label: "tick cadence" },
  { value: 3, suffix: "", label: "strategies backtested" },
  { value: 2, suffix: "", label: "execution algos" },
];

/** Counter = GSAP job. Text updates are data, motion stays transform/opacity. */
export default function StatBand() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      root.current?.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
        const end = Number(el.dataset.count || "0");
        const obj = { v: 0 };
        gsap.to(obj, {
          v: end,
          duration: 1.2,
          ease: "power2.out",
          scrollTrigger: { trigger: el, start: "top 90%", once: true },
          onUpdate: () => {
            el.textContent = `${Math.round(obj.v)}${el.dataset.suffix || ""}`;
          },
        });
      });
    },
    { scope: root }
  );

  return (
    <div ref={root} className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-hairline bg-[var(--color-hairline)] md:grid-cols-4">
      {STATS.map((s) => (
        <div key={s.label} className="bg-bg px-6 py-8 text-center">
          <div data-count={s.value} data-suffix={s.suffix} className="tnum text-3xl font-semibold tracking-tight">
            0{s.suffix}
          </div>
          <div className="mt-1 text-xs uppercase tracking-[0.14em] text-fg-muted">{s.label}</div>
        </div>
      ))}
    </div>
  );
}
