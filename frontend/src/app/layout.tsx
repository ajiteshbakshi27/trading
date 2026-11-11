import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import RegisterSW from "@/components/RegisterSW";

const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = {
  title: { default: "Parakh — test your trade before the market does", template: "%s · Parakh" },
  description:
    "An AI trading coach for Indian markets: check trade ideas before you place them, journal your Zerodha trades, get honest autopsies and track your calibration.",
  manifest: "/manifest.webmanifest",
  applicationName: "Parakh",
};

export const viewport: Viewport = { themeColor: "#030712" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} dark`}>
      <body>
        {children}
        <RegisterSW />
      </body>
    </html>
  );
}
