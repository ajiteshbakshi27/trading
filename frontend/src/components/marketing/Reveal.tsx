"use client";
import { useRef, type ReactNode } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

gsap.registerPlugin(ScrollTrigger, useGSAP);

/**
 * Shared scroll reveal (GSAP job, transform + opacity only).
 * Under reduced-motion, children render in their final state.
 */
export default function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li" | "header";
}) {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      gsap.from(root.current, {
        y: 16,
        opacity: 0,
        duration: 0.6,
        delay,
        ease: "expo.out",
        scrollTrigger: { trigger: root.current, start: "top 88%", once: true },
      });
    },
    { scope: root }
  );

  return (
    <Tag ref={root as never} className={className}>
      {children}
    </Tag>
  );
}
