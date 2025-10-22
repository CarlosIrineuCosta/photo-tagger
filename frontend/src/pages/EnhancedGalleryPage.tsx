import { useCallback, useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { EnhancedTagGallery } from "@/components/EnhancedTagGallery"
import { StatusStrip } from "@/components/StatusStrip"
import { Topbar } from "@/components/Topbar"
import { useStatusLog } from "@/context/status-log"
import { fetchGallery } from "@/lib/api"
import EnhancedTaggingAPI, { type EnhancedGalleryItem, type TagCandidate } from "@/lib/enhanced_api"

export function EnhancedGalleryPage() {
  const [items, setItems] = useState<EnhancedGalleryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [itemState, setItemState] = useState<Record<string, { selected: string[]; saved: boolean; excluded_tags: string[]; tag_stack: TagCandidate[] }>>({})
  const [enhancedMode, setEnhancedMode] = useState(true)
  const { push: addLog } = useStatusLog()

  const loadGallery = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      addLog({ message: "Loading gallery..." })

      const galleryItems = await fetchGallery()

      if (enhancedMode) {
        addLog({ message: "Processing tags with enhanced system..." })
        const enhancedItems = await EnhancedTaggingAPI.enhanceGalleryItems(galleryItems)
        setItems(enhancedItems)
        addLog({ message: `Enhanced processing complete for ${enhancedItems.length} images` })
      } else {
        // Convert to enhanced format for compatibility
        const convertedItems: EnhancedGalleryItem[] = galleryItems.map((item) => ({
          ...item,
          width: item.width ?? undefined,
          height: item.height ?? undefined,
          label_source: item.label_source ?? "fallback",
          display_tags: item.labels.map((label) => ({
            name: label.name,
            score: label.score,
            is_excluded: false,
            is_user_added: false,
          })),
          tag_stack: [],
          excluded_tags: [],
        }))
        setItems(convertedItems)
      }

      // Initialize item state
      const initialState: Record<string, { selected: string[]; saved: boolean; excluded_tags: string[]; tag_stack: TagCandidate[] }> = {}
      galleryItems.forEach(item => {
        initialState[item.path] = {
          selected: item.selected,
          saved: item.saved,
          excluded_tags: [],
          tag_stack: []
        }
      })
      setItemState(initialState)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to load gallery"
      setError(errorMessage)
      addLog({ message: `Error: ${errorMessage}`, level: "error" })
    } finally {
      setLoading(false)
    }
  }, [enhancedMode, addLog])

  useEffect(() => {
    loadGallery()
  }, [loadGallery])

  const handleToggleLabel = useCallback((itemPath: string, label: TagCandidate) => {
    setItemState(prev => {
      const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
      const isSelected = currentState.selected.includes(label.name)

      const newSelected = isSelected
        ? currentState.selected.filter(name => name !== label.name)
        : [...currentState.selected, label.name]

      return {
        ...prev,
        [itemPath]: {
          ...currentState,
          selected: newSelected,
          saved: newSelected.length > 0
        }
      }
    })

    addLog({
      message: `${label.is_user_added ? "User tag" : "Tag"} "${label.name}" ${itemState[itemPath]?.selected.includes(label.name) ? "removed from" : "added to"} ${itemPath.split('/').pop()}`,
      level: "info"
    })
  }, [itemState, addLog])

  const handleExcludeTag = useCallback(async (itemPath: string, tagName: string) => {
    try {
      addLog({ message: `Excluding tag "${tagName}" from ${itemPath.split('/').pop()}` })

      if (enhancedMode) {
        // Call the enhanced API to exclude the tag
        const response = await EnhancedTaggingAPI.excludeTag({
          image_path: itemPath,
          tag_name: tagName
        })

        if (response.status === "success" && response.next_tag) {
          // Update the item state with the new tag from the stack
          setItemState(prev => {
            const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
            return {
              ...prev,
              [itemPath]: {
                ...currentState,
                excluded_tags: [...currentState.excluded_tags, tagName],
                tag_stack: currentState.tag_stack.slice(1) // Remove the used tag from stack
              }
            }
          })

          // Update the items to show the new tag
          setItems(prev => prev.map(item => {
            if (item.path === itemPath) {
              // Replace the excluded tag with the next one from stack
              const newDisplayTags = item.display_tags.map(tag =>
                tag.name === tagName ? response.next_tag! : tag
              )
              return {
                ...item,
                display_tags: newDisplayTags,
                tag_stack: item.tag_stack.slice(1)
              }
            }
            return item
          }))

          addLog({ message: `Replaced excluded tag "${tagName}" with "${response.next_tag.name}"` })
        } else {
          // No more tags in stack
          setItemState(prev => {
            const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
            return {
              ...prev,
              [itemPath]: {
                ...currentState,
                excluded_tags: [...currentState.excluded_tags, tagName]
              }
            }
          })

          // Remove the tag from display
          setItems(prev => prev.map(item => {
            if (item.path === itemPath) {
              return {
                ...item,
                display_tags: item.display_tags.filter(tag => tag.name !== tagName)
              }
            }
            return item
          }))

          addLog({ message: `Excluded tag "${tagName}" (no more tags in stack)` })
        }
      } else {
        // Just update the local state in non-enhanced mode
        setItemState(prev => {
          const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
          return {
            ...prev,
            [itemPath]: {
              ...currentState,
              excluded_tags: [...currentState.excluded_tags, tagName]
            }
          }
        })

        // Remove the tag from display
        setItems(prev => prev.map(item => {
          if (item.path === itemPath) {
            return {
              ...item,
              display_tags: item.display_tags.filter(tag => tag.name !== tagName)
            }
          }
          return item
        }))

        addLog({ message: `Excluded tag "${tagName}"` })
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to exclude tag"
      addLog({ message: `Error excluding tag: ${errorMessage}`, level: "error" })
    }
  }, [enhancedMode, addLog])

  const handleAddUserTag = useCallback(async (itemPath: string, tagName: string) => {
    try {
      addLog({ message: `Adding user tag "${tagName}" to ${itemPath.split('/').pop()}` })

      if (enhancedMode) {
        // Call the enhanced API to process the user tag
        const response = await EnhancedTaggingAPI.addUserTag({
          image_path: itemPath,
          tag_name: tagName
        })

        // Update the items to include the new tag
        setItems(prev => prev.map(item => {
          if (item.path === itemPath) {
            return {
              ...item,
              display_tags: [...item.display_tags, response.processed_tag]
            }
          }
          return item
        }))

        // Update the item state to include the new tag
        setItemState(prev => {
          const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
          return {
            ...prev,
            [itemPath]: {
              ...currentState,
              selected: [...currentState.selected, response.processed_tag.name],
              saved: true
            }
          }
        })

        addLog({
          message: `Added user tag "${response.processed_tag.name}"${response.processed_tag.original_synonym ? ` (from "${response.processed_tag.original_synonym}")` : ""}`,
          level: "success"
        })
      } else {
        // Just add the tag directly in non-enhanced mode
        const newTag: TagCandidate = {
          name: tagName,
          score: 1.0,
          is_excluded: false,
          is_user_added: true
        }

        // Update the items to include the new tag
        setItems(prev => prev.map(item => {
          if (item.path === itemPath) {
            return {
              ...item,
              display_tags: [...item.display_tags, newTag]
            }
          }
          return item
        }))

        // Update the item state to include the new tag
        setItemState(prev => {
          const currentState = prev[itemPath] || { selected: [], saved: false, excluded_tags: [], tag_stack: [] }
          return {
            ...prev,
            [itemPath]: {
              ...currentState,
              selected: [...currentState.selected, tagName],
              saved: true
            }
          }
        })

        addLog({ message: `Added user tag "${tagName}"`, level: "success" })
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to add user tag"
      addLog({ message: `Error adding user tag: ${errorMessage}`, level: "error" })
    }
  }, [enhancedMode, addLog])

  if (loading) {
    return (
      <div className="flex h-screen flex-col">
        <Topbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="mb-4 text-lg">Loading gallery...</div>
            <div className="text-sm text-muted-foreground">Please wait while we process your images</div>
          </div>
        </div>
        <StatusStrip items={[]} />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-screen flex-col">
        <Topbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="mb-4 text-lg text-destructive">Error</div>
            <div className="mb-4 text-sm text-muted-foreground">{error}</div>
            <Button onClick={loadGallery}>Try Again</Button>
          </div>
        </div>
        <StatusStrip items={[]} />
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col">
      <Topbar />
      <div className="border-b border-line/60 bg-panel px-6 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Enhanced Gallery</h1>
          <div className="flex items-center gap-4">
            <Button
              variant={enhancedMode ? "default" : "outline"}
              size="sm"
              onClick={() => setEnhancedMode(!enhancedMode)}
            >
              {enhancedMode ? "Enhanced Mode" : "Standard Mode"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={loadGallery}
            >
              Refresh
            </Button>
          </div>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-6">
        <EnhancedTagGallery
          items={items}
          itemState={itemState}
          onToggleLabel={handleToggleLabel}
          onExcludeTag={handleExcludeTag}
          onAddUserTag={handleAddUserTag}
        />
      </div>
      <StatusStrip items={[]} />
    </div>
  )
}
