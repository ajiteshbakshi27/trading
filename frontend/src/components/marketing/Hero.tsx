"use client";
import { useRef } from "react";
import Link from "next/link";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { ArrowRight, BookOpen } from "lucide-react";
import TerminalFrame from "./TerminalFrame";

gsap.registerPlugin(ScrollTrigger, useGSAP);

const LINES = [
  ["The", "crowd", "is"],
  ["a", "signal", "you"],
  ["can", "fade."],
];

export default function Hero() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      // Entry: word stagger, transform + opacity only.
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".hero-word", {
          yPercent: 110,
          opacity: 0,
          duration: 0.9,
          ease: "expo.out",
          stagger: 0.045,
        });
        gsap.from(".hero-fade", {
          y: 16,
          opacity: 0,
          duration: 0.7,
          ease: "expo.out",
          stagger: 0.06,
          delay: 0.25,
        });
      });

      // Hero gesture: pinned scrub, desktop only (mobile keeps native scroll).
      mm.add("(min-width: 768px) and (prefers-reduced-motion: no-preference)", () => {
        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: ".hero-track",
            start: "top top",
            end: "bottom bottom",
            scrub: 1.2,
          },
        });
        tl.to(".hero-copy", { yPercent: -12, opacity: 0.15, ease: "none" }, 0)
          .fromTo(
            ".hero-frame",
            { yPercent: 6, scale: 0.96, rotateX: 5 },
            { yPercent: -6, scale: 1, rotateX: 0, ease: "none" },
            0
          )
          .fromTo(".hero-glow", { opacity: 0.5 }, { opacity: 0.15, ease: "none" }, 0);
      });

      return () => mm.revert();
    },
    { scope: root }
  );

  return (
    <section ref={root} className="relative">
      {/* 200vh track + sticky viewport = pin without layout writes (desktop only) */}
      <div className="hero-track relative h-auto md:h-[200vh]">
        <div className="relative flex items-start md:sticky md:top-0 md:h-screen md:items-center">
          {/* single restrained glow, not a mesh gradient */}
          <div className="hero-glow pointer-events-none absolute left-1/2 top-[-20%] h-[560px] w-[900px] -translate-x-1/2 rounded-full bg-accent/10 blur-[140px]" />

          <div className="relative mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 py-24 md:grid-cols-12 md:gap-10 md:py-0">
            {/* copy */}
            <div className="hero-copy md:col-span-6">
              <p className="hero-fade section-label mb-5">Quantum × HFT × sentiment</p>
              <h1 className="text-[clamp(2.5rem,5.4vw,4.25rem)] font-semibold leading-[1.04] tracking-[-0.03em]">
                {LINES.map((line, i) => (
                  <span key={i} className="mk-split-line">
                    {line.map((w) => (
                      <span key={w} className="mk-split-mask">
                        <span className="hero-word mk-split-inner">{w}</span>
                        {" "}
                      </span>
                    ))}
                  </span>
                ))}
              </h1>
              <p className="hero-fade mt-6 max-w-lg text-base leading-relaxed text-fg-muted">
                PennyLane portfolio weights, live order-flow imbalance and social-sentiment fades —
                on one desk, with paper-trading execution and a kill switch that actually fires.
              </p>
              <div className="hero-fade mt-8 flex flex-wrap items-center gap-3">
                <Link href="/dashboard" className="mk-btn mk-btn-primary">
                  Open live terminal <ArrowRight className="h-4 w-4" />
                </Link>
                <a
                  href={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
                  target="_blank"
                  rel="noreferrer"
                  className="mk-btn mk-btn-ghost"
                >
                  <BookOpen className="h-4 w-4" /> API &amp; docs
                </a>
              </div>
              <dl className="hero-fade mt-10 flex flex-wrap gap-x-10 gap-y-3 text-sm">
                {[["Optimizer", "QAOA · PennyLane"], ["Flow model", "Cont OFI"], ["Quotes", "IEX / AV"]].map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-xs uppercase tracking-[0.14em] text-fg-muted">{k}</dt>
                    <dd className="tnum mt-0.5 font-medium">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* product frame */}
            <div className="hero-frame md:col-span-6" style={{ perspective: "1200px" }}>
              <TerminalFrame />
            </div>
          </div>

          {/* scroll cue */}
          <div className="hero-fade absolute bottom-8 left-1/2 hidden -translate-x-1/2 items-center gap-3 text-xs uppercase tracking-[0.2em] text-fg-muted md:flex">
            Scroll
            <span className="block h-10 w-px bg-hairline" />
          </div>
        </div>
      </div>
    </section>
  );
}
