import type { ReportDetail, ReportListResponse } from "./types";

/**
 * Browser → backend: NEXT_PUBLIC_API_URL (CORS allows localhost:3000).
 * Server components → backend: BACKEND_URL (compose network) with the public URL as fallback.
 * `token` is the Clerk session JWT (SAAS §3); null when auth is disabled.
 */
// `||`, not `??`: the Docker build arg can inline these as EMPTY STRINGS,
// which are defined-but-useless — they must still fall through.
export const PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function serverApiUrl(): string {
  return process.env.BACKEND_URL || PUBLIC_API_URL;
}

export function authHeaders(token: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function fetchReports(
  params?: { ticker?: string; limit?: number; offset?: number },
  token: string | null = null,
): Promise<ReportListResponse> {
  const search = new URLSearchParams();
  if (params?.ticker) search.set("ticker", params.ticker);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.size > 0 ? `?${search}` : "";
  const res = await fetch(`${serverApiUrl()}/api/reports${qs}`, {
    cache: "no-store",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error(`Failed to load reports (${res.status})`);
  return res.json();
}

export async function fetchReport(
  id: string,
  token: string | null = null,
): Promise<ReportDetail | null> {
  const res = await fetch(`${serverApiUrl()}/api/reports/${id}`, {
    cache: "no-store",
    headers: authHeaders(token),
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to load report (${res.status})`);
  return res.json();
}
