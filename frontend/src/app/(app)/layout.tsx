import Navbar from "@/components/Navbar";
import QuantCopilot from "@/components/QuantCopilot";
import AuthGuard from "@/components/AuthGuard";
import HydrationFlag from "@/components/HydrationFlag";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="space-bg min-h-screen">
        <HydrationFlag />
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 pb-16 pt-6">{children}</main>
        <footer className="mx-auto max-w-7xl px-4 pb-24 text-[11px] leading-relaxed text-slate-500">
          Parakh is an analysis and journaling tool. It is not a SEBI-registered investment adviser or research
          analyst and does not recommend buying or selling any security. Historical patterns and simulations do not
          guarantee future results. Trading in equities and derivatives involves risk of loss.
        </footer>
        <QuantCopilot />
      </div>
    </AuthGuard>
  );
}
