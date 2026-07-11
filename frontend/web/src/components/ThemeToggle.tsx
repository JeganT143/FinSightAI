"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";

function getStoredOrSystemTheme(): Theme {
  const stored = localStorage.getItem("finsight-theme");
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function SunIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.8" />
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        d="M12 2.5v2.2M12 19.3v2.2M21.5 12h-2.2M4.7 12H2.5M18.4 5.6l-1.55 1.55M7.15 16.85l-1.55 1.55M18.4 18.4l-1.55-1.55M7.15 7.15 5.6 5.6"
      />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
        d="M20.5 14.2A8.5 8.5 0 1 1 9.8 3.5a7 7 0 0 0 10.7 10.7Z"
      />
    </svg>
  );
}

/** Day Desk / Night Desk toggle (DESIGN.md §2.0) — persisted, system-aware. */
export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    // Reads a browser-only API (localStorage/matchMedia) that doesn't exist
    // during SSR, so it can only run post-mount — not a derived-state effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setTheme(getStoredOrSystemTheme());
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem("finsight-theme", next);
    document.documentElement.setAttribute("data-theme", next);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "dark" ? "Switch to day desk (light theme)" : "Switch to night desk (dark theme)"}
      title={theme === "dark" ? "Day desk" : "Night desk"}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface text-text-muted transition-colors hover:text-brand"
    >
      {/* Render nothing until mounted to avoid a hydration mismatch with the inline script's choice */}
      {theme === "dark" ? <SunIcon /> : theme === "light" ? <MoonIcon /> : <span className="h-4 w-4" />}
    </button>
  );
}
