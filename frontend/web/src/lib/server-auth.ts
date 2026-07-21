import "server-only";

import { auth } from "@clerk/nextjs/server";
import { CLERK_ENABLED } from "./auth-config";

/** The Clerk session token for server-component fetches; null when auth is off. */
export async function serverToken(): Promise<string | null> {
  if (!CLERK_ENABLED) return null;
  const { getToken } = await auth();
  return getToken();
}
