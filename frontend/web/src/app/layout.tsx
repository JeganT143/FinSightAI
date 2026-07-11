import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Newsreader } from "next/font/google";
import Image from "next/image";
import Link from "next/link";
import Script from "next/script";
import { ThemeToggle } from "@/components/ThemeToggle";
import "./globals.css";

// Sets data-theme on <html> BEFORE hydration, so there's no flash of the
// wrong theme. beforeInteractive is only valid directly inside app/layout.tsx
// (or pages/_document.js) — that's why this lives here rather than in its
// own component (Next.js's lint rule can't see through that indirection).
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("finsight-theme");
    var theme = stored === "light" || stored === "dark"
      ? stored
      : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  style: ["normal", "italic"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "FinSightAI — adversarial AI equity research",
  description:
    "A team of AI analysts researches any US-listed stock in parallel, grounded in SEC filings, reviewed by an adversarial critic before publication.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${plexSans.variable} ${plexMono.variable} ${newsreader.variable}`}
    >
      <body className="min-h-screen bg-bg font-sans text-text antialiased">
        <Script id="theme-init" strategy="beforeInteractive">
          {THEME_INIT_SCRIPT}
        </Script>
        <header className="border-b border-border">
          <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-surface">
                <Image src="/logo.png" alt="" width={26} height={26} priority />
              </span>
              <span className="text-lg font-semibold tracking-tight text-text">
                FinSight<span className="text-brand">AI</span>
              </span>
            </Link>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-7 font-mono text-sm uppercase tracking-widest">
                <Link href="/" className="text-text-muted transition-colors hover:text-brand">
                  Console
                </Link>
                <Link href="/reports" className="text-text-muted transition-colors hover:text-brand">
                  Ledger
                </Link>
              </div>
              <ThemeToggle />
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-10 sm:px-6">{children}</main>
        <footer className="mx-auto max-w-6xl px-4 pb-8 sm:px-6">
          <p className="border-t border-border pt-5 text-sm text-text-muted">
            Research demo — not investment advice. Grounded in yfinance + SEC EDGAR data.
          </p>
        </footer>
      </body>
    </html>
  );
}
