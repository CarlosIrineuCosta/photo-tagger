/**
 * Enhanced API client for the improved tagging system.
 */

import type { ApiGalleryItem, ApiLabel } from "./api"

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
  display_tags: TagCandidate[]
  tag_stack: TagCandidate[]
  excluded_tags: string[]
}

export class EnhancedTaggingAPI {
  /**
   * Process tag scores using the enhanced tagging system.
   */
  static async processTags(request: EnhancedTagRequest): Promise<EnhancedTagResponse> {
    const response = await fetch("/api/enhanced/process-tags", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `Request failed with status ${response.status}`)
    }

    return response.json()
  }

  /**
   * Exclude a tag and get the next best candidate from the stack.
   */
  static async excludeTag(request: ExcludeTagRequest): Promise<ExcludeTagResponse> {
    const response = await fetch("/api/enhanced/exclude-tag", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `Request failed with status ${response.status}`)
    }

    return response.json()
  }

  /**
   * Add a user tag and process it through the post-processor.
   */
  static async addUserTag(request: AddUserTagRequest): Promise<AddUserTagResponse> {
    const response = await fetch("/api/enhanced/add-user-tag", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `Request failed with status ${response.status}`)
    }

    return response.json()
  }

  /**
   * Get the current synonym map.
   */
  static async getSynonyms(): Promise<SynonymMapResponse> {
    const response = await fetch("/api/enhanced/synonyms")

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `Request failed with status ${response.status}`)
    }

    return response.json()
  }

  /**
   * Update the synonym map.
   */
  static async updateSynonyms(synonymMap: Record<string, string>): Promise<{ status: string; updated_count: number }> {
    const response = await fetch("/api/enhanced/update-synonyms", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(synonymMap),
    })

    if (!response.ok) {
      const message = await response.text()
      throw new Error(message || `Request failed with status ${response.status}`)
    }

    return response.json()
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
