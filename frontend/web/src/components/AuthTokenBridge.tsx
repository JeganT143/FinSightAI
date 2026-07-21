"use client";

/**
 * Bridges Clerk's useAuth().getToken to a context every client component can
 * consume WITHOUT knowing whether Clerk exists. When auth is disabled the
 * default context value returns null and no Clerk hook is ever called —
 * useAuth outside a ClerkProvider throws, so the bridge component is only
 * mounted inside one (see layout.tsx).
 */

import { useAuth } from "@clerk/nextjs";
import { createContext, useCallback, useContext } from "react";

type TokenGetter = () => Promise<string | null>;

const TokenContext = createContext<TokenGetter>(async () => null);

export function ClerkTokenBridge({ children }: { children: React.ReactNode }) {
  const { getToken } = useAuth();
  const getter = useCallback(async () => (await getToken()) ?? null, [getToken]);
  return <TokenContext.Provider value={getter}>{children}</TokenContext.Provider>;
}

/** A stable async getter for the current API token (null when auth is off). */
export function useAuthToken(): TokenGetter {
  return useContext(TokenContext);
}
