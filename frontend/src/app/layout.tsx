import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = {
  title: { default: "QuantPulse AI — quantum + HFT trading terminal", template: "%s · QuantPulse AI" },
  description:
    "Quantum portfolio weights, HFT order-flow execution and crowd-sentiment fades in one live trading terminal.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} dark`}>
      <body>{children}</body>
    </html>
  );
}
