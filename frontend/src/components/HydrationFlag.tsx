"use client";
import { useEffect } from "react";

/**
 * Marks the document as hydrated. Zero-cost production hook that lets
 * end-to-end tests wait for interactivity instead of guessing with sleeps
 * (dev-mode route compiles make fixed timeouts flaky).
 */
export default function HydrationFlag() {
  useEffect(() => {
    document.documentElement.setAttribute("data-hydrated", "1");
  }, []);
  return null;
}
