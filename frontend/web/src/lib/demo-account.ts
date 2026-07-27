/**
 * Public demo account (portfolio/reviewer access) — a real Clerk user,
 * created once via the normal sign-up flow. Shown on the sign-in and sign-up
 * cards so visitors never need to ask for credentials or create their own
 * account.
 *
 * Uses Clerk's `+clerk_test` dev-instance convention: it auto-verifies with
 * a fixed code (424242) instead of emailing a real one, since nobody owns an
 * actual inbox at this address. Only works while Clerk is on a development
 * instance — swap to a real, owned mailbox (dropping `+clerk_test`) when
 * moving to a Clerk Production instance for the live deploy.
 */
export const DEMO_EMAIL = "explore+clerk_test@finsight.ai";
export const DEMO_PASSWORD = "finsightai";
