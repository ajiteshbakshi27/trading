"use client";
import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

const CHIPS = [
  "PennyLane QAOA",
  "Cont order-flow imbalance",
  "VWAP / TWAP",
  "Sharpe · Sortino · VaR · CVaR",
  "Kill switch",
  "Paper execution",
  "Prediction-market edges",
  "Social fades",
];

/**
 * Marquee = GSAP job, transform-only. Pauses on hover/focus (a11y),
 * and renders a static, readable list under reduced-motion.
 */
export default function TickerMarquee() {
  const root = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const track = root.current?.querySelector<HTMLElement>(".marquee-track");
      if (!track) return;
      const loop = gsap.to(track, {
        xPercent: -50,
        duration: 28,
        ease: "none",
        repeat: -1,
        modifiers: { xPercent: (v) => `${parseFloat(v) % 50}` },
      });
      const el = root.current;
      const pause = () => gsap.to(loop, { timeScale: 0, duration: 0.4, ease: "power1.out" });
      const play = () => gsap.to(loop, { timeScale: 1, duration: 0.4, ease: "power1.out" });
      el?.addEventListener("mouseenter", pause);
      el?.addEventListener("focusin", pause);
      el?.addEventListener("mouseleave", play);
      el?.addEventListener("focusout", play);
      return () => {
        el?.removeEventListener("mouseenter", pause);
        el?.removeEventListener("focusin", pause);
        el?.removeEventListener("mouseleave", play);
        el?.removeEventListener("focusout", play);
        loop.kill();
      };
    },
    { scope: root }
  );

  return (
    <div
      ref={root}
      role="region"
      aria-label="Platform capabilities"
      tabIndex={0}
      className="relative overflow-hidden border-y border-hairline py-5"
    >
      <div className="marquee-track flex w-max gap-3 pr-3">
        {[0, 1].map((copy) => (
          <div key={copy} className="flex shrink-0 gap-3" aria-hidden={copy === 1}>
            {CHIPS.map((c) => (
              <span
                key={c}
                className="whitespace-nowrap rounded-full border border-hairline px-4 py-1.5 text-xs text-fg-muted"
              >
                {c}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
