/**
 * Enhanced API client for the improved tagging system.
 */

import type { ApiGalleryItem, ApiLabel } from "./api"

const explicitBaseEnv =
  (typeof import.meta !== "undefined" && (import.meta as any)?.env?.VITE_API_BASE
    ? String((import.meta as any).env.VITE_API_BASE).trim()
    : undefined) ??
  (typeof process !== "undefined" && process.env?.VITE_API_BASE
    ? String(process.env.VITE_API_BASE).trim()
    : undefined)

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

export interface TagCandidate {
  name: string
  score: number
  is_excluded: boolean
  is_user_added: boolean
  original_synonym?: string
}

export interface EnhancedTagRequest {
  image_path: string
  tag_scores: Array<{ tag: string; score: number }>
  user_tags?: string[]
  max_display_tags?: number
  tag_stack_multiplier?: number
}

export interface EnhancedTagResponse {
  display_tags: TagCandidate[]
  tag_stack: TagCandidate[]
  excluded_tags: string[]
}

export interface ExcludeTagRequest {
  image_path: string
  tag_name: string
}

export interface ExcludeTagResponse {
  status: string
  next_tag?: TagCandidate
}

export interface AddUserTagRequest {
  image_path: string
  tag_name: string
}

export interface AddUserTagResponse {
  status: string
  processed_tag: TagCandidate
}

export interface SynonymMapResponse {
  synonym_map: Record<string, string>
  reverse_synonym_map: Record<string, string[]>
}

export interface EnhancedGalleryItem extends Omit<ApiGalleryItem, 'width' | 'height' | 'label_source'> {
  width?: number | undefined  // Remove null from the type
  height?: number | undefined  // Remove null from the type
  label_source?: string  // Make it optional
  requires_processing?: boolean
  display_tags: TagCandidate[]
  tag_stack: TagCandidate[]
  excluded_tags: string[]
}

export class EnhancedTaggingAPI {
  /**
   * Process tag scores using the enhanced tagging system.
   */
  static async processTags(requestData: EnhancedTagRequest): Promise<EnhancedTagResponse> {
    return request<EnhancedTagResponse>("/api/enhanced/process-tags", {
      method: "POST",
      body: JSON.stringify(requestData),
    })
  }

  /**
   * Exclude a tag and get the next best candidate from the stack.
   */
  static async excludeTag(requestData: ExcludeTagRequest): Promise<ExcludeTagResponse> {
    return request<ExcludeTagResponse>("/api/enhanced/exclude-tag", {
      method: "POST",
      body: JSON.stringify(requestData),
    })
  }

  /**
   * Add a user tag and process it through the post-processor.
   */
  static async addUserTag(requestData: AddUserTagRequest): Promise<AddUserTagResponse> {
    return request<AddUserTagResponse>("/api/enhanced/add-user-tag", {
      method: "POST",
      body: JSON.stringify(requestData),
    })
  }

  /**
   * Get the current synonym map.
   */
  static async getSynonyms(): Promise<SynonymMapResponse> {
    return request<SynonymMapResponse>("/api/enhanced/synonyms")
  }

  /**
   * Update the synonym map.
   */
  static async updateSynonyms(synonymMap: Record<string, string>): Promise<{ status: string; updated_count: number }> {
    return request<{ status: string; updated_count: number }>("/api/enhanced/update-synonyms", {
      method: "POST",
      body: JSON.stringify(synonymMap),
    })
  }

  /**
   * Convert regular API gallery items to enhanced gallery items.
   * This is a helper function to bridge the existing API with the enhanced system.
   */
  static async enhanceGalleryItems(
    items: ApiGalleryItem[],
    maxDisplayTags: number = 10,
    tagStackMultiplier: number = 2
  ): Promise<EnhancedGalleryItem[]> {
    const enhancedItems: EnhancedGalleryItem[] = []

    for (const item of items) {
      if (item.requires_processing) {
        enhancedItems.push({
          ...item,
          width: item.width || undefined,
          height: item.height || undefined,
          label_source: item.label_source || "fallback",
          requires_processing: true,
          display_tags: [],
          tag_stack: [],
          excluded_tags: []
        })
        continue
      }

      try {
        // Convert existing labels to tag scores format
        const tagScores = item.labels.map((label: ApiLabel) => ({
          tag: label.name,
          score: label.score
        }))

        // Process tags through the enhanced system
        const enhancedResponse = await this.processTags({
          image_path: item.path,
          tag_scores: tagScores,
          max_display_tags: maxDisplayTags,
          tag_stack_multiplier: tagStackMultiplier
        })

        // Create enhanced item
        const enhancedItem: EnhancedGalleryItem = {
          ...item,
          width: item.width || undefined,
          height: item.height || undefined,
          label_source: item.label_source || "fallback",
          requires_processing: item.requires_processing || false,
          display_tags: enhancedResponse.display_tags,
          tag_stack: enhancedResponse.tag_stack,
          excluded_tags: enhancedResponse.excluded_tags
        }

        enhancedItems.push(enhancedItem)
      } catch (error) {
        console.error("Failed to enhance item:", item.path, error)
        // Fall back to original item if enhancement fails
        const fallbackItem: EnhancedGalleryItem = {
          ...item,
          width: item.width || undefined,
          height: item.height || undefined,
          label_source: item.label_source || "fallback",
          requires_processing: item.requires_processing || false,
          display_tags: item.labels.map(label => ({
            name: label.name,
            score: label.score,
            is_excluded: false,
            is_user_added: false
          })),
          tag_stack: [],
          excluded_tags: []
        }
        enhancedItems.push(fallbackItem)
      }
    }

    return enhancedItems
  }
}

export default EnhancedTaggingAPI
