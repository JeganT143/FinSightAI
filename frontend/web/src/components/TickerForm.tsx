"use client";

import { useEffect, useRef, useState } from "react";

/** Order-entry bar (DESIGN.md §4.1). `/` focuses it from anywhere. */
export function TickerForm({
  onSubmit,
  disabled,
}: {
  onSubmit: (ticker: string) => void;
  disabled: boolean;
}) {
  const [ticker, setTicker] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const valid = /^[A-Z]{1,5}$/.test(ticker);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "/" && document.activeElement?.tagName !== "INPUT") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <form
      className="flex w-full max-w-2xl overflow-hidden rounded-lg border border-border bg-surface focus-within:border-brand/70"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid && !disabled) onSubmit(ticker);
      }}
    >
      <label htmlFor="ticker" className="sr-only">
        Stock ticker
      </label>
      <span className="hidden items-center border-r border-border px-4 font-mono text-[13px] uppercase tracking-widest text-text-muted sm:flex">
        Ticker
      </span>
      <input
        ref={inputRef}
        id="ticker"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 5))}
        placeholder="NVDA"
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        className="w-full bg-transparent px-4 py-4 font-mono text-2xl uppercase tracking-[0.12em] text-text placeholder:text-text-muted/40 focus:outline-none disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={!valid || disabled}
        className="whitespace-nowrap bg-brand px-6 text-[15px] font-semibold uppercase tracking-wide text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {disabled ? "Running…" : "Run research"}
      </button>
    </form>
  );
}
