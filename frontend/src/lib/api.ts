const DEFAULT_API_BASE = import.meta.env.DEV ? "http://127.0.0.1:8010" : ""
const API_BASE = ((import.meta.env.VITE_API_BASE as string | undefined) ?? DEFAULT_API_BASE).replace(/\/$/, "")

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  return `${API_BASE}${normalizedPath}`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    const message = await response.text()
    throw new Error(message || `Request failed with status ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
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

export async function updateConfig(
  payload: Partial<Pick<ApiConfig, "root" | "max_images">>
): Promise<{ status: string; config: ApiConfig }> {
  return request<{ status: string; config: ApiConfig }>("/api/config", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}
