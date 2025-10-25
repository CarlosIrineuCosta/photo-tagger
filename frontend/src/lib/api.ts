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

export type ApiMedoidCluster = {
  cluster_type: "folder" | "tag" | "embedding" | string
  cluster_tag: string
  label_hint: string
  cluster_size: number
  cosine_to_centroid: number
}

export type ReviewStage = "new" | "needs_tags" | "has_draft" | "saved" | "blocked"

export type ApiGalleryItem = {
  id: string
  filename: string
  path: string
  thumb: string
  width?: number | null
  height?: number | null
  medoid: boolean
  medoid_folder?: string
  medoid_clusters?: ApiMedoidCluster[]
  medoid_cluster_size?: number | null
  medoid_cosine_to_centroid?: number | null
  saved: boolean
  selected: string[]
  label_source?: "scores" | "sidecar" | "fallback"
  requires_processing?: boolean
  labels: ApiLabel[]
  stage: ReviewStage
  first_seen: number
  last_processed?: number | null
  last_saved?: number | null
  blocked_reason?: string | null
  pending?: string[]
  is_new?: boolean
  is_modified?: boolean
}

export type GalleryResponse = {
  items: ApiGalleryItem[]
  next_cursor?: string | null
  has_more: boolean
  total: number
  summary: {
    total: number
    counts: Record<ReviewStage, number>
  }
}

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

export async function fetchGallery(cursor?: string, limit?: number, stageFilter?: ReviewStage): Promise<GalleryResponse> {
  const params = new URLSearchParams()
  if (cursor) params.append("cursor", cursor)
  if (limit) params.append("limit", limit.toString())
  if (stageFilter) params.append("stage", stageFilter)

  const query = params.toString()
  const url = query ? `/api/gallery?${query}` : "/api/gallery"
  return request<GalleryResponse>(url)
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
  features?: {
    llm_enhancer?: boolean
  }
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
  description?: string | null
  canonical_count?: number | null
  supports_bulk?: boolean
}

export type OrphanTagSummary = {
  name: string
  occurrences: number
  suggested_group_id?: string | null
  suggested_label_id?: string | null
  label_hint?: string | null
  confidence?: number | null
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
  label_id?: string
}

export type PromoteOrphanTagResponse = {
  status: string
  tag: string
  group: string
  group_label: string
  total: number
  created_group: boolean
  occurrences?: number
  label_id?: string
}

export async function promoteOrphanTag(payload: PromoteOrphanTagPayload): Promise<PromoteOrphanTagResponse> {
  return request<PromoteOrphanTagResponse>("/api/tags/promote", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export type BulkPromoteAction = {
  tag: string
  target_group?: string
  new_group_label?: string
  label_id?: string
}

export type BulkPromoteRequest = {
  actions: BulkPromoteAction[]
}

export type BulkPromoteResult = {
  tag: string
  status: string
  group?: string
  group_label?: string
  total?: number
  created_group?: boolean
  occurrences?: number
  label_id?: string
  detail?: string
}

export type BulkPromoteResponse = {
  results: BulkPromoteResult[]
}

export async function promoteOrphanTagsBulk(payload: BulkPromoteRequest): Promise<BulkPromoteResponse> {
  return request<BulkPromoteResponse>("/api/tags/promote/bulk", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export type SuggestGroupResponse = {
  suggested_group_id: string
  confidence: number
  reasoning?: string
  alternatives: Array<{
    group_id: string
    group_label: string
    confidence: number
  }>
  label_id?: string
}

export async function suggestGroupForTag(tag: string, context?: string): Promise<SuggestGroupResponse> {
  const params = new URLSearchParams()
  params.append("tag", tag)
  if (context) {
    params.append("context", context)
  }
  return request<SuggestGroupResponse>(`/api/tags/suggest-group?${params.toString()}`)
}

export type GraduationEntry = {
  label_id: string
  canonical_label: string
  group: string
  promotions: Array<{
    tag: string
    label_id?: string
    group: string
    group_label: string
    created_group?: boolean
    occurrences?: number
    status: string
    promoted_at?: string
    resolved_at?: string
  }>
  count: number
}

export type GraduationsResponse = {
  graduations: GraduationEntry[]
  stats: {
    pending: number
    resolved: number
  }
}

export async function fetchGraduations(): Promise<GraduationsResponse> {
  return request<GraduationsResponse>("/api/tags/graduations")
}

export async function resolveGraduation(labelId: string, action: "resolve" | "skip" = "resolve"): Promise<{
  status: string
  label_id: string
  action: string
  updated_count: number
}> {
  return request(`/api/tags/graduations/${labelId}/resolve?action=${action}`, {
    method: "POST",
  })
}

export async function prefetchThumbnails(paths?: string[], overwrite = false): Promise<{ job_id: string; scheduled: number }> {
  return request("/api/thumbs/prefetch", {
    method: "POST",
    body: JSON.stringify({ paths: paths ?? [], overwrite }),
  })
}
