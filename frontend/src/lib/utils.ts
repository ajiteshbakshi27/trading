import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Intl formatters, cached per currency. */
export function fmtMoney(v: number, currency = "USD") {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency", currency, maximumFractionDigits: 2,
    }).format(v);
  } catch {
    return `${v.toLocaleString()} ${currency}`;
  }
}

export function fmtPct(v: number, digits = 2) {
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}
