import type { SupabaseClient } from "@supabase/supabase-js";

export class WorkspaceError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
export function databaseError(error: { code?: string; message: string }): never {
  if (error.code === "PGRST202" || error.code === "42883") {
    throw new WorkspaceError(503, "Pembaruan workspace cloud belum dipasang. Administrator perlu menjalankan SQL 202611040002_cloud_workspace.sql.");
  }
  const status: Record<string, number> = { "42501": 403, "P0002": 404, "23505": 409, "22023": 422 };
  if (error.code && status[error.code]) throw new WorkspaceError(status[error.code], error.message);
  if (error.code?.startsWith("22")) throw new WorkspaceError(422, "Format nilai, ID, atau tanggal tidak valid.");
  throw new WorkspaceError(503, "Operasi database belum berhasil. Coba kembali atau periksa konfigurasi workspace.");
}
export async function capabilities(client: SupabaseClient, organization: string) {
  const { data, error } = await client.rpc("baylab_workspace_capabilities", { p_organization: organization });
  if (error?.code === "PGRST202" || error?.code === "42883") {
    return { workspace_ready: false, schema_version: 1,
      message: "Aktifkan formulasi, eksperimen, dan peringkat dengan menjalankan SQL pembaruan workspace cloud." };
  }
  if (error) databaseError(error);
  return data;
}
export async function action(client: SupabaseClient, organization: string, operation: string,
  payload: Record<string, unknown>, recordId: string | null = null) {
  const { data, error } = await client.rpc("baylab_workspace_action", {
    p_organization: organization, p_action: operation, p_payload: payload, p_record_id: recordId,
  });
  if (error) databaseError(error);
  return data;
}
export interface CloudRecord {
  id: string; kind: string; data: Record<string, unknown>; created_at: string;
}
export async function records(client: SupabaseClient, organization: string, kind?: string) {
  const result: CloudRecord[] = [];
  // PostgREST caps individual responses. Fetch explicit pages rather than silently truncate.
  for (let offset = 0; ; offset += 500) {
    let query = client.from("baylab_records").select("id,kind,data,created_at")
      .eq("organization_slug", organization).eq("archived", false)
      .order("created_at", { ascending: false }).order("id", { ascending: true }).range(offset, offset + 499);
    if (kind) query = query.eq("kind", kind);
    const { data, error } = await query;
    if (error) databaseError(error);
    result.push(...(data as CloudRecord[]));
    if (data.length < 500) return result;
    if (result.length >= 10000) throw new WorkspaceError(413, "Data terlalu banyak untuk satu tampilan. Hubungi administrator untuk pengarsipan atau paginasi lanjutan.");
  }
}
