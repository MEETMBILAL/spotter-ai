import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Vercel Edge Middleware — distributed rate limiting at the CDN edge.
 *
 * Runs BEFORE requests hit backend processes, giving edge-level protection
 * across serverless invocations.
 */

const LIMITS: Record<string, { max: number; windowMs: number }> = {
  "/api/analyze": { max: 10, windowMs: 60_000 },
  "/api/heatmap": { max: 20, windowMs: 60_000 },
};
const DEFAULT_LIMIT = { max: 100, windowMs: 60_000 };

export const config = {
  matcher: ["/api/:path*"],
};

export default async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const ip =
    request.headers.get("x-real-ip") ??
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    "unknown";

  const limit = LIMITS[pathname] ?? DEFAULT_LIMIT;

  try {
    const { kv } = await import("@vercel/kv").catch(() => ({ kv: null }));
    if (kv) {
      const key = `rl:${pathname}:${ip}`;
      const count = await kv.incr(key);
      if (count === 1) {
        await kv.expire(key, Math.ceil(limit.windowMs / 1000));
      }
      if (count > limit.max) {
        return new NextResponse(
          JSON.stringify({
            error: {
              code: "rate_limited",
              message: "Too many requests. Please slow down.",
            },
          }),
          {
            status: 429,
            headers: {
              "Content-Type": "application/json",
              "Retry-After": String(Math.ceil(limit.windowMs / 1000)),
            },
          }
        );
      }
    }
  } catch {
    // Fail open when KV is unavailable
  }

  return NextResponse.next();
}
