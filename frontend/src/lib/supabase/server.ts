import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

// Only Route Handlers use this client. They can persist refreshed cookies.
// Browser JS never receives access/refresh tokens.
export async function createClient() {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error("SUPABASE_NOT_CONFIGURED");
  const store = await cookies();
  return createServerClient(url, key, {
    cookieOptions: {
      httpOnly: true, sameSite: "strict", path: "/",
      secure: process.env.VERCEL === "1" || process.env.BAYLAB_SECURE_COOKIES === "true",
    },
    global: { fetch: (input, init) => fetch(input, { ...init, cache: "no-store", signal: AbortSignal.timeout(20000) }) },
    cookies: {
      getAll: () => store.getAll(),
      setAll: (values) => {
        for (const { name, value, options } of values) store.set(name, value, options);
      },
    },
  });
}
