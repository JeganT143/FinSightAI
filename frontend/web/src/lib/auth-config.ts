/**
 * Auth feature flag (SAAS §3), mirroring the backend's AUTH_MODE:
 * no publishable key = Clerk fully absent — no provider, no middleware
 * protection, no tokens — and the backend acts as the dev user. Local dev
 * and CI build without any Clerk account.
 */
export const CLERK_ENABLED = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

/** Clerk appearance mapped onto the existing token set (SAAS_DESIGN §4) —
 * the auth UI must not look like a different product. */
export const clerkAppearance = {
  variables: {
    colorPrimary: "var(--brand)",
    colorBackground: "var(--surface)",
    colorText: "var(--text)",
    colorTextSecondary: "var(--text-muted)",
    colorInputBackground: "var(--bg)",
    colorInputText: "var(--text)",
    borderRadius: "0.5rem",
    fontFamily: "var(--font-plex-sans)",
  },
  elements: {
    card: "border border-[var(--border)] shadow-none",
    footer: "hidden",
  },
};
