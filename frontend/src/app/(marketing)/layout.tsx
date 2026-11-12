import SmoothScroll from "@/components/marketing/SmoothScroll";
import HydrationFlag from "@/components/HydrationFlag";

export const metadata = {
  title: "Parakh — test your trade before the market does",
  description:
    "An analysis and journaling tool for Indian retail traders: check your own trade ideas, see what your habits cost, and measure your calibration. Not investment advice.",
};

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <SmoothScroll>
      <div className="relative min-h-screen overflow-x-clip bg-bg text-fg">
        <HydrationFlag />
        {children}
      </div>
    </SmoothScroll>
  );
}
