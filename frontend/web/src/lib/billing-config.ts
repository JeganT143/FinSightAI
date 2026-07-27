/**
 * Billing feature flag, independent of AUTH_MODE/CLERK_ENABLED: off until
 * Stripe is actually configured. Flip NEXT_PUBLIC_BILLING_ENABLED=true and
 * rebuild once real Stripe keys are wired up (backend/core/config.py
 * STRIPE_* + this) — no other code changes needed to bring pricing/upgrade
 * UI back.
 */
export const BILLING_ENABLED = process.env.NEXT_PUBLIC_BILLING_ENABLED === "true";
