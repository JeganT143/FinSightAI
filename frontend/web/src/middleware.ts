/**
 * Route protection (SAAS §3.1). Public: landing, pricing, auth pages, and
 * Next internals; everything else redirects unauthenticated visitors to
 * sign-in. With no Clerk key configured the middleware is a pass-through —
 * dev parity with the backend's AUTH_MODE=disabled.
 */

import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/pricing",
  "/sign-in(.*)",
  "/sign-up(.*)",
]);

const clerkEnabled = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

export default clerkEnabled
  ? clerkMiddleware(async (auth, req) => {
      if (!isPublicRoute(req)) {
        await auth.protect();
      }
    })
  : () => NextResponse.next();

export const config = {
  matcher: [
    // Everything except static assets and Next internals.
    "/((?!_next|.*\\.(?:png|svg|jpg|jpeg|ico|css|js|woff2?)).*)",
    "/(api|trpc)(.*)",
  ],
};
