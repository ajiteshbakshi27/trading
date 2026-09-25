import Navbar from "@/components/Navbar";
import QuantCopilot from "@/components/QuantCopilot";
import AuthGuard from "@/components/AuthGuard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <div className="space-bg min-h-screen">
        <Navbar />
        <main className="mx-auto max-w-7xl px-4 pb-16 pt-6">{children}</main>
        <QuantCopilot />
      </div>
    </AuthGuard>
  );
}
