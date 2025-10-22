const explicitBaseEnv = (import.meta.env.VITE_API_BASE as string | undefined)?.trim()
const EXPLICIT_API_BASE = explicitBaseEnv ? explicitBaseEnv.replace(/\/$/, "") : null

function buildUrl(path: string, base: string | null): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  return base ? `${base}${normalizedPath}` : normalizedPath
}

async function performRequest<T>(path: string, base: string | null, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json")
  }

  const response = await fetch(
    buildUrl(path, base),
    {
      ...init,
      headers,
    }
  )

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with status ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (EXPLICIT_API_BASE) {
    try {
      return await performRequest<T>(path, EXPLICIT_API_BASE, init)
    } catch (error) {
      if (error instanceof TypeError) {
        // Network error when using explicit base — fall back to same-origin proxy.
        return await performRequest<T>(path, null, init)
      }
      throw error
    }
  }
  return performRequest<T>(path, null, init)
}

export type ApiLabel = {
  name: string
  score: number
}

export type ApiGalleryItem = {
  id: string
  filename: string
  path: string
  thumb: string
  width?: number | null
  height?: number | null
  medoid: boolean
  saved: boolean
  selected: string[]
  label_source?: "scores" | "sidecar" | "fallback"
  labels: ApiLabel[]
}

export type GalleryResponse = ApiGalleryItem[]

export type TagRequestPayload = {
  filename: string
  approved_labels: string[]
}

export type ExportRequestPayload = {
  mode: "csv" | "sidecars" | "both"
}

export type ExportResponse = {
  status: string
  files: string[]
}

export type ProcessResponse = {
  status: string
  run_id?: string
}

export async function fetchGallery(): Promise<GalleryResponse> {
  return request<GalleryResponse>("/api/gallery")
}

export async function saveTag(payload: TagRequestPayload): Promise<{ status: string; saved: boolean }> {
  return request<{ status: string; saved: boolean }>("/api/tag", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function exportData(payload: ExportRequestPayload): Promise<ExportResponse> {
  return request<ExportResponse>("/api/export", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function processImages(): Promise<ProcessResponse> {
  return request<ProcessResponse>("/api/process", {
    method: "POST",
  })
}

export type ApiConfig = {
  root: string
  labels_file: string
  run_dir: string
  thumb_cache: string
  max_images: number
  topk: number
  model_name: string
}

export async function fetchConfig(): Promise<ApiConfig> {
  return request<ApiConfig>("/api/config")
}

export async function updateConfig(payload: Partial<ApiConfig>): Promise<{ status: string; config: ApiConfig }> {
  return request<{ status: string; config: ApiConfig }>("/api/config", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export type TagGroupSummary = {
  id: string
  label: string
  path: string
  tags: string[]
}

export type OrphanTagSummary = {
  name: string
  occurrences: number
}

export type TagSummaryResponse = {
  groups: TagGroupSummary[]
  orphan_tags: OrphanTagSummary[]
  stats: Record<string, number>
}

export async function fetchTagSummary(): Promise<TagSummaryResponse> {
  return request<TagSummaryResponse>("/api/tags/summary")
}

export type MutateTagPayload = {
  group: string
  tag: string
}

export async function addTagToGroup(payload: MutateTagPayload): Promise<{ status: string; group: string; tag: string; total: number }> {
  return request<{ status: string; group: string; tag: string; total: number }>("/api/tags/item", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function deleteTagFromGroup(payload: MutateTagPayload): Promise<{ status: string; group: string; tag: string; total: number }> {
  return request<{ status: string; group: string; tag: string; total: number }>("/api/tags/item", {
    method: "DELETE",
    body: JSON.stringify(payload),
  })
}

export type PromoteOrphanTagPayload = {
  tag: string
  target_group?: string
  new_group_label?: string
}

export type PromoteOrphanTagResponse = {
  status: string
  tag: string
  group: string
  group_label: string
  total: number
  created_group: boolean
  occurrences?: number
}

export async function promoteOrphanTag(payload: PromoteOrphanTagPayload): Promise<PromoteOrphanTagResponse> {
  return request<PromoteOrphanTagResponse>("/api/tags/promote", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}
