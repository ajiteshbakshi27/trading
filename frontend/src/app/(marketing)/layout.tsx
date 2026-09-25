import SmoothScroll from "@/components/marketing/SmoothScroll";

export const metadata = {
  title: "QuantPulse AI — trade the signal, not the crowd",
  description:
    "Live trading terminal combining PennyLane quantum portfolio weights, HFT order-flow execution, and social-sentiment fades.",
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <SmoothScroll>
      <div className="relative min-h-screen overflow-x-clip bg-bg text-fg">{children}</div>
    </SmoothScroll>
  );
}
