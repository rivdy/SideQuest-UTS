import { randomBytes, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { action, capabilities, records, WorkspaceError } from "@/lib/supabase/workspace";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const ORG = "baylab_cloud_org";
const CSRF = "baylab_cloud_csrf";
class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) { super(message); }
}
const response = (body: unknown, status = 200) => NextResponse.json(body, {
  status, headers: { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" },
});
const cookieOptions = () => ({ httpOnly: true, sameSite: "strict" as const, path: "/",
  secure: process.env.VERCEL === "1" || process.env.BAYLAB_SECURE_COOKIES === "true", maxAge: 60 * 60 * 24 * 7 });
function stringField(body: Record<string, unknown>, key: string, min: number, max: number) {
  const value = body[key];
  if (typeof value !== "string" || value.length < min || value.length > max) throw new ApiError(422, "Isian " + key + " tidak valid.");
  return value;
}
async function readBody(request: NextRequest, allowed: string[]) {
  const length = Number(request.headers.get("content-length"));
  if (length > 32768) throw new ApiError(413, "Permintaan terlalu besar.");
  const reader = request.body?.getReader();
  if (!reader) throw new ApiError(422, "Isian diperlukan.");
  let size = 0; const chunks: Uint8Array[] = [];
  while (true) {
    const { value, done } = await reader.read(); if (done) break;
    size += value.length;
    if (size > 32768) { await reader.cancel(); throw new ApiError(413, "Permintaan terlalu besar."); }
    chunks.push(value);
  }
  let body;
  try { body = JSON.parse(Buffer.concat(chunks).toString("utf8")); } catch { throw new ApiError(422, "JSON tidak valid."); }
  if (!body || typeof body !== "object" || Array.isArray(body) || Object.keys(body).some(k => !allowed.includes(k))) throw new ApiError(422, "Payload tidak sesuai.");
  return body as Record<string, unknown>;
}
async function membership(client: Awaited<ReturnType<typeof createClient>>, userId: string, slug: string) {
  const { data, error } = await client.from("baylab_memberships")
    .select("organization_slug,role,display_name,active,baylab_organizations(name)")
    .eq("user_id", userId).eq("organization_slug", slug).eq("active", true).maybeSingle();
  if (error) throw new ApiError(503, "Tabel organisasi Supabase belum siap. Administrator perlu menjalankan SQL setup BAYLab.");
  if (!data) throw new ApiError(403, "Akun belum terdaftar sebagai anggota aktif organisasi ini. Hubungi administrator.");
  const organization = data.baylab_organizations as unknown as { name: string } | null;
  if (!organization) throw new ApiError(403, "Organisasi tidak tersedia.");
  return { name: data.display_name as string, role: data.role as string,
    organization: { slug: data.organization_slug as string, name: organization.name } };
}
async function handle(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const path = (await context.params).path.join("/");
  const cloud = process.env.BAYLAB_AUTH_PROVIDER === "supabase";
  if ((path === "auth/config" || path === "cloud-config") && request.method === "GET") return response({ provider: cloud ? "supabase" : "local", workspace: cloud ? "cloud" : "full" });
  if (!cloud) return response({ detail: "Backend lokal tidak tersedia pada rute ini." }, 503);
  try {
    const mutation = !["GET", "HEAD"].includes(request.method);
    if (mutation) {
      const origin = request.headers.get("origin");
      const allowed = new Set([request.nextUrl.origin, `${request.nextUrl.protocol}//${request.headers.get("host")}`, ...(process.env.BAYLAB_ALLOWED_ORIGINS || "").split(",").map(v => v.trim()).filter(Boolean)]);
      if ((origin && !allowed.has(origin)) || request.headers.get("sec-fetch-site") === "cross-site") throw new ApiError(403, "Origin tidak diizinkan.");
    }
    const client = await createClient();
    const store = await cookies();
    if (path === "auth/login" && request.method === "POST") {
      const body = await readBody(request, ["organization", "email", "password"]);
      const slug = stringField(body, "organization", 2, 40).trim();
      if (!/^[a-z0-9][a-z0-9-]{1,39}$/.test(slug)) throw new ApiError(422, "Kode organisasi tidak valid.");
      const email = stringField(body, "email", 3, 180).trim().toLowerCase();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new ApiError(422, "Email tidak valid.");
      const password = stringField(body, "password", 1, 128);
      const { data, error } = await client.auth.signInWithPassword({ email, password });
      if (error || !data.user) throw new ApiError(error?.status === 429 ? 429 : 401, error?.status === 429 ? "Terlalu banyak percobaan. Coba kembali nanti." : "Email atau kata sandi Supabase tidak sesuai, atau akun belum dikonfirmasi.");
      try {
        const profile = await membership(client, data.user.id, slug);
        const csrf = randomBytes(32).toString("hex");
        store.set(ORG, slug, cookieOptions()); store.set(CSRF, csrf, cookieOptions());
        return response({ user: { ...profile, email: data.user.email }, csrf_token: csrf, provider: "supabase" });
      } catch (error) {
        await client.auth.signOut({ scope: "local" }); store.delete(ORG); store.delete(CSRF); throw error;
      }
    }
    // getUser verifies identity with Auth and refreshes expired sessions through setAll.
    const { data: { user }, error: identityError } = await client.auth.getUser();
    if (identityError || !user) throw new ApiError(401, "Silakan masuk dengan akun Supabase organisasi.");
    if (mutation) {
      const expected = store.get(CSRF)?.value || ""; const supplied = request.headers.get("x-csrf-token") || "";
      if (!expected || expected.length !== supplied.length || !timingSafeEqual(Buffer.from(expected), Buffer.from(supplied))) throw new ApiError(403, "Token CSRF tidak valid. Muat ulang halaman.", "csrf_invalid");
    }
    if (path === "auth/logout" && request.method === "POST") {
      const { error } = await client.auth.signOut({ scope: "local" });
      if (error) throw new ApiError(503, "Logout belum berhasil. Coba kembali.");
      store.delete(ORG); store.delete(CSRF); return response({ ok: true });
    }
    const slug = store.get(ORG)?.value;
    if (!slug) throw new ApiError(401, "Pilih organisasi dengan masuk kembali.");
    const profile = await membership(client, user.id, slug);
    if (path === "auth/session" && request.method === "GET") {
      let csrf = store.get(CSRF)?.value;
      if (!csrf) { csrf = randomBytes(32).toString("hex"); store.set(CSRF, csrf, cookieOptions()); }
      return response({ user: { ...profile, email: user.email }, csrf_token: csrf, provider: "supabase" });
    }
    if (path === "auth/password" && request.method === "POST") {
      const body = await readBody(request, ["old_password", "new_password"]);
      const oldPassword = stringField(body, "old_password", 1, 128);
      const newPassword = stringField(body, "new_password", 12, 128);
      const { error: verifyError } = await client.auth.signInWithPassword({ email: user.email!, password: oldPassword });
      if (verifyError) throw new ApiError(401, "Kata sandi saat ini tidak sesuai.");
      const { error } = await client.auth.updateUser({ password: newPassword });
      if (error) throw new ApiError(422, "Perubahan kata sandi ditolak oleh kebijakan Supabase. Periksa pengaturan password atau autentikasi ulang.");
      await client.auth.signOut({ scope: "global" }); store.delete(ORG); store.delete(CSRF);
      return response({ ok: true });
    }
    if (path === "auth/users" && request.method === "GET") {
      if (profile.role !== "admin") throw new ApiError(403, "Hanya administrator.");
      const { data, error } = await client.from("baylab_memberships").select("display_name,role,active")
        .eq("organization_slug", slug).eq("active", true);
      if (error) throw new ApiError(503, "Daftar anggota belum dapat dimuat.");
      return response((data || []).map(row => ({ name: row.display_name, role: row.role, email: "Dikelola melalui Supabase Auth" })));
    }
    if (path === "workspace/capabilities" && request.method === "GET") {
      return response(await capabilities(client, slug));
    }
    const assessmentMatch = path.match(/^workspace\/formulations\/([a-f0-9-]{36})\/assessment$/i);
    const archiveMatch = path.match(/^workspace\/experiments\/([a-f0-9-]{36})$/i);
    const operations: Record<string, { name: string; fields: string[]; status: number }> = {
      "workspace/formulations": { name: "create_formulation", fields: ["name","aroma_profile","ingredients","notes","data_origin"], status: 201 },
      "workspace/experiments": { name: "create_experiment", fields: ["formulation_id","batch_id","protocol","source_ref","measured_on","initial_h2o2","final_h2o2","ph","temperature_c","duration_days","homogeneous","aroma_intensity","notes","data_origin","confirmed_actual"], status: 201 },
      "workspace/rank": { name: "rank", fields: ["formulation_ids","weights","comparison_protocol"], status: 200 },
    };
    if (request.method === "POST" && operations[path]) {
      const operation = operations[path];
      if (operation.name !== "rank" && !["admin","formulator"].includes(profile.role)) throw new ApiError(403, "Akun pembaca tidak dapat mengubah data.");
      const body = await readBody(request, operation.fields);
      return response(await action(client, slug, operation.name, body), operation.status);
    }
    if (request.method === "PUT" && assessmentMatch) {
      if (!["admin","formulator"].includes(profile.role)) throw new ApiError(403, "Akun pembaca tidak dapat mengubah data.");
      const body = await readBody(request, ["comparison_protocol","oxidation","solubility","compatibility","temperature","aroma"]);
      return response(await action(client, slug, "assess_formulation", body, assessmentMatch[1]));
    }
    if (request.method === "DELETE" && archiveMatch) {
      if (!["admin","formulator"].includes(profile.role)) throw new ApiError(403, "Akun pembaca tidak dapat mengubah data.");
      return response(await action(client, slug, "archive_experiment", {}, archiveMatch[1]));
    }
    if (path.startsWith("workspace/") && request.method === "GET") {
      if (path === "workspace/model/status") return response({ can_train: false, eligible_rows: 0, groups: 0, message: "Pelatihan model belum terhubung pada deployment Supabase. Gunakan aplikasi lokal." });
      const kinds: Record<string, string> = { "workspace/formulations": "formulation", "workspace/experiments": "experiment", "workspace/model/runs": "model_run" };
      if (path === "workspace/overview" || kinds[path]) {
        const data = await records(client, slug, kinds[path]);
        if (path === "workspace/overview") return response({
          formulations: data.filter(r => r.kind === "formulation").length,
          experiments: data.filter(r => r.kind === "experiment").length,
          real_experiments: data.filter(r => r.kind === "experiment" && r.data.data_origin === "real").length,
          synthetic_experiments: data.filter(r => r.kind === "experiment" && r.data.data_origin === "synthetic").length,
          model_runs: data.filter(r => r.kind === "model_run").length,
        });
        return response(data.map(row => ({ ...row.data, id: row.id, created: Date.parse(row.created_at) / 1000 })));
      }
    }
    if (path.startsWith("rag/") || path.startsWith("chemistry/")) throw new ApiError(503, "Layanan RAG/RDKit masih tersedia pada aplikasi lokal; belum dihubungkan ke deployment Supabase.");
    if (path.startsWith("workspace/") || path === "auth/users") throw new ApiError(503, "Operasi ini belum tersedia di cloud. Pelatihan model tetap lokal; pengelolaan anggota dilakukan oleh administrator Supabase.");
    throw new ApiError(404, "Endpoint tidak tersedia.");
  } catch (error) {
    if (error instanceof ApiError || error instanceof WorkspaceError) return response({ detail: error.message, ...(error instanceof ApiError && error.code ? { code: error.code } : {}) }, error.status);
    return response({ detail: "Supabase belum dapat dihubungi atau konfigurasi belum lengkap. Periksa URL dan Publishable Key di environment deployment." }, 503);
  }
}
export { handle as GET, handle as POST, handle as PUT, handle as DELETE, handle as PATCH };
