import Link from "next/link";
import HydrationFlag from "@/components/HydrationFlag";

export const metadata = {
  title: "Parakh — try it free",
  description: "X-ray your tradebook or check a trade idea. No sign-up needed.",
};

/** Public "try before you sign up" pages: no login, nothing saved. */
export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-bg min-h-screen">
      <HydrationFlag />
      <header className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4">
        <Link href="/" className="text-lg font-bold text-white">Parakh</Link>
        <nav className="flex flex-wrap items-center gap-4 text-sm text-slate-300">
          <Link href="/xray" className="hover:text-white">Tradebook X-ray</Link>
          <Link href="/try" className="hover:text-white">Check a trade</Link>
          <Link href="/login" className="hover:text-white">Log in</Link>
          <Link href="/signup" className="rounded-lg bg-emerald-500 px-3 py-1.5 font-semibold text-black hover:bg-emerald-400">Sign up free</Link>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-4">{children}</main>
      <footer className="mx-auto max-w-5xl px-4 pb-16 text-[11px] leading-relaxed text-slate-500">
        Parakh is an analysis and journaling tool. It is not a SEBI-registered investment adviser or research
        analyst and does not recommend buying or selling any security. Historical patterns and simulations do not
        guarantee future results. Trading in equities and derivatives involves risk of loss.
      </footer>
    </div>
  );
}
