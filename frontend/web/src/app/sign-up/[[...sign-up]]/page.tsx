"use client";

import { SignUp } from "@clerk/nextjs";
import { useState } from "react";
import { DemoCredentials } from "@/components/DemoCredentials";
import { clerkAppearance } from "@/lib/auth-config";

/**
 * Sign-up with explicit consent (SAAS_DESIGN §4): the disclaimer checkbox is
 * required and unchecked by default — the one moment SAAS §9's compliance
 * posture asks for explicit acknowledgment, not just a footer line.
 */
export default function SignUpPage() {
  const [accepted, setAccepted] = useState(false);

  return (
    <div className="flex flex-col items-center gap-6 pt-10">
      <DemoCredentials />
      <label className="flex max-w-md cursor-pointer items-start gap-3 rounded-lg border border-border bg-surface px-4 py-3.5">
        <input
          type="checkbox"
          checked={accepted}
          onChange={(e) => setAccepted(e.target.checked)}
          className="mt-1 h-4 w-4 accent-[var(--brand)]"
        />
        <span className="text-[15px] leading-relaxed text-text">
          I understand FinSightAI provides research information,{" "}
          <strong>not personalized investment advice</strong>.
        </span>
      </label>

      {accepted ? (
        <SignUp appearance={clerkAppearance} />
      ) : (
        <p className="font-mono text-[13px] uppercase tracking-widest text-text-muted">
          Accept the statement above to create an account
        </p>
      )}
    </div>
  );
}
