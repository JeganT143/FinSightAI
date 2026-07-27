"use client";

import { useState } from "react";
import { DEMO_EMAIL, DEMO_PASSWORD } from "@/lib/demo-account";

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-border bg-bg px-3 py-2">
      <div className="min-w-0">
        <p className="font-mono text-[11px] uppercase tracking-widest text-text-muted">{label}</p>
        <p className="truncate font-mono text-[13px] text-text">{value}</p>
      </div>
      <button
        type="button"
        onClick={copy}
        className="shrink-0 rounded-md border border-border px-2.5 py-1 font-mono text-[11px] uppercase tracking-widest text-text-muted transition-colors hover:border-brand hover:text-brand"
      >
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

/** Sits above the Clerk sign-in/sign-up card: no account needed, no asking
 * the operator for access — copy, paste, explore. */
export function DemoCredentials() {
  return (
    <div className="w-full max-w-md space-y-2.5 rounded-xl border border-border bg-surface p-4">
      <p className="text-[15px] text-text">
        Want to explore FinSightAI? You don&apos;t need to create an account — use this credential
        to explore.
      </p>
      <CopyField label="Email" value={DEMO_EMAIL} />
      <CopyField label="Password" value={DEMO_PASSWORD} />
    </div>
  );
}
