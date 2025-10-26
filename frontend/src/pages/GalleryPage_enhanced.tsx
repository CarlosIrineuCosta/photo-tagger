import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { CommandBar } from "@/components/CommandBar"
import { BlockingOverlay } from "@/components/BlockingOverlay"
import { GalleryGridEnhanced } from "@/components/GalleryGrid_enhanced"
import { WorkflowSidebar, type WorkflowMessage, type WorkflowStep } from "@/components/WorkflowSidebar"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import {
  exportData,
  fetchGallery,
  processImages,
  saveTag,
  type ApiGalleryItem,
  type GalleryResponse,
  type ReviewStage,
} from "@/lib/api"
import EnhancedTaggingAPI, { type EnhancedGalleryItem, type TagCandidate } from "@/lib/enhanced_api"
import { useStatusLog } from "@/context/status-log"
import { useMediaQuery } from "@/hooks/use-media-query"
import { useIntersectionObserver } from "@/hooks/useIntersectionObserver"

type FilterKey = "medoidsOnly" | "unapprovedOnly" | "hideAfterSave" | "centerCrop"

type ItemState = {
  selected: string[]
  original: string[]
  saved: boolean
  excluded_tags: string[]
  tag_stack: TagCandidate[]
}

const DEFAULT_FILTERS: Record<FilterKey, boolean> = {
  medoidsOnly: false,
  unapprovedOnly: false,
  hideAfterSave: false,
  centerCrop: false,
}

const WORKFLOW_STEPS: WorkflowStep[] = [
  { title: "Scan", detail: "Found 1,248 images", status: "done" },
  { title: "Thumbnails", detail: "Cached to thumb_cache/", status: "done" },
  { title: "Embeddings", detail: "CLIP ViT-L/14 complete", status: "done" },
  { title: "Scores", detail: "Top labels ready", status: "done" },
  { title: "Enhanced review", detail: "Approve or adjust tags with enhanced features", status: "active" },
  { title: "Export", detail: "CSV + XMP sidecars", status: "pending" },
]

export function GalleryPageEnhanced() {
  const { push: pushStatus } = useStatusLog()
  const isMobile = useMediaQuery("(max-width: 1023px)")
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [pageSize, setPageSize] = useState(25)
  const [workflowOpen, setWorkflowOpen] = useState(false)
  const [items, setItems] = useState<EnhancedGalleryItem[]>([])
  const [itemState, setItemState] = useState<Record<string, ItemState>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [needsProcessing, setNeedsProcessing] = useState(true)
  const [saving, setSaving] = useState(false)
  const [recentlySaved, setRecentlySaved] = useState<string[]>([])
  const [blockingMessage, setBlockingMessage] = useState<{ title: string; message?: string; tone?: "default" | "warning" } | null>(null)
  const [workflowMessages, setWorkflowMessages] = useState<WorkflowMessage[]>([])
  const [summary, setSummary] = useState<GalleryResponse["summary"] | null>(null)
  const [stageFilter, setStageFilter] = useState<ReviewStage | "all">("all")
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const cursorRef = useRef<string | undefined>(undefined)
  const [hasMore, setHasMore] = useState(true)
  const [loadMoreRef, isIntersecting] = useIntersectionObserver({
    threshold: 0.1,
    rootMargin: "120px",
  })

  const appendWorkflowMessage = useCallback((text: string, tone: WorkflowMessage["tone"] = "info") => {
    const id =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random()}`
    const timestamp = new Date().toLocaleTimeString()
    setWorkflowMessages((prev) => {
      const next = [...prev, { id, text, tone, timestamp }]
      return next.slice(-6)
    })
  }, [])

  const normalizeList = useCallback((values: string[] | undefined) => {
    if (!values || values.length === 0) {
      return []
    }
    const unique = Array.from(new Set(values.map((value) => value.trim()))).filter(Boolean)
    return unique.sort((a, b) => a.localeCompare(b))
  }, [])

  const listsEqual = useCallback((a: string[], b: string[]) => {
    if (a.length !== b.length) {
      return false
    }
    return a.every((value, index) => value === b[index])
  }, [])

  const convertToEnhancedItems = useCallback(
    (apiItems: ApiGalleryItem[]): EnhancedGalleryItem[] =>
      apiItems.map((item) => ({
        ...item,
        width: item.width ?? undefined,
        height: item.height ?? undefined,
        label_source: item.label_source ?? "fallback",
        requires_processing: item.requires_processing ?? false,
        display_tags: item.labels.map<TagCandidate>((label) => ({
          name: label.name,
          score: label.score,
          is_excluded: false,
          is_user_added: false,
        })),
        tag_stack: [],
        excluded_tags: [],
      })),
    []
  )

  useEffect(() => {
    cursorRef.current = cursor
  }, [cursor])

  const loadGallery = useCallback(
    async (reset = false) => {
      setLoading(true)
      if (reset) {
        setBlockingMessage({ title: "Loading gallery…", message: "Fetching latest tags and thumbnails.", tone: "warning" })
      }
      try {
        const stageParam = stageFilter === "all" ? undefined : stageFilter
        const currentCursor = reset ? undefined : cursorRef.current
        const data = await fetchGallery(currentCursor, pageSize, stageParam)
        const apiItems = Array.isArray(data?.items) ? data.items : []

        let enhancedBatch: EnhancedGalleryItem[] = []
        try {
          enhancedBatch = await EnhancedTaggingAPI.enhanceGalleryItems(apiItems)
          if (enhancedBatch.length > 0) {
            pushStatus({ message: `Enhanced processing complete for ${enhancedBatch.length} images`, level: "success" })
            if (reset) {
              appendWorkflowMessage(`Enhanced processing complete for ${enhancedBatch.length} images.`, "success")
            }
          }
        } catch (err) {
          console.error("Enhanced processing failed:", err)
          pushStatus({ message: "Enhanced processing failed; using baseline tags.", level: "error" })
          appendWorkflowMessage("Enhanced processing failed; using baseline tags.", "warning")
          enhancedBatch = convertToEnhancedItems(apiItems)
        }

        if (enhancedBatch.length === 0 && apiItems.length > 0) {
          enhancedBatch = convertToEnhancedItems(apiItems)
        }

        let combined: EnhancedGalleryItem[] = []
        setItems((prev) => {
          const base = reset ? [] : prev
          combined = [...base, ...enhancedBatch]
          return combined
        })

        const nextState: Record<string, ItemState> = {}
        combined.forEach((item) => {
          const normalized = normalizeList(item.selected)
          nextState[item.path] = {
            selected: normalized,
            original: normalized,
            saved: item.saved ?? false,
            excluded_tags: item.excluded_tags || [],
            tag_stack: item.tag_stack || [],
          }
        })
        setItemState(nextState)

        setSummary(data?.summary ?? null)
        setCursor(data?.next_cursor ?? undefined)
        setHasMore(Boolean(data?.has_more))
        const requiresProcessing = combined.some((item) => item.requires_processing)
        setNeedsProcessing(requiresProcessing)
        if (requiresProcessing && reset) {
          pushStatus({ message: "Please run Process images again.", level: "info" })
          appendWorkflowMessage("Images require reprocessing. Run Process images again.", "warning")
        }
        setError(null)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to load gallery"
        setError(message)
        setSummary(null)
        appendWorkflowMessage(`Gallery load failed: ${message}`, "error")
      } finally {
        setLoading(false)
        if (reset) {
          setBlockingMessage(null)
        }
      }
    },
    [appendWorkflowMessage, convertToEnhancedItems, normalizeList, pageSize, pushStatus, stageFilter]
  )

  useEffect(() => {
    setCursor(undefined)
    cursorRef.current = undefined
    setHasMore(true)
    setItems([])
    setItemState({})
    setSummary(null)
    setError(null)
    void loadGallery(true)
  }, [loadGallery, stageFilter])

  useEffect(() => {
    if (isIntersecting && hasMore && !loading) {
      void loadGallery(false)
    }
  }, [hasMore, isIntersecting, loadGallery, loading])

  const itemMap = useMemo(() => {
    const map: Record<string, EnhancedGalleryItem> = {}
    items.forEach((item) => {
      map[item.path] = item
    })
    return map
  }, [items])

  const recentlySavedSet = useMemo(() => new Set(recentlySaved), [recentlySaved])

  const toggleLabelApproval = useCallback((itemPath: string, label: TagCandidate) => {
    setItemState((prev) => {
      const persisted = itemMap[itemPath]
      const current = prev[itemPath] ?? {
        selected: normalizeList(persisted?.selected),
        original: normalizeList(persisted?.selected),
        saved: persisted?.saved ?? false,
        excluded_tags: [],
        tag_stack: []
      }
      const exists = current.selected.includes(label.name)
      const nextSelected = exists
        ? current.selected.filter((name) => name !== label.name)
        : [...current.selected, label.name]
      const normalizedSelected = normalizeList(nextSelected)
      const originalNormalized = normalizeList(current.original)
      const isSameAsOriginal = listsEqual(normalizedSelected, originalNormalized)
      const persistedSaved = persisted?.saved ?? false
      const nextSaved = isSameAsOriginal ? persistedSaved : false
      return {
        ...prev,
        [itemPath]: {
          selected: normalizedSelected,
          original: current.original,
          saved: nextSaved,
          excluded_tags: current.excluded_tags,
          tag_stack: current.tag_stack
        },
      }
    })

    const wasSelected = itemState[itemPath]?.selected.includes(label.name)
    const action = wasSelected ? "removed from" : "added to"
    const isUserAdded = label.is_user_added || false
    pushStatus({
      message: `${isUserAdded ? "User tag" : "Tag"} "${label.name}" ${action} ${itemPath.split('/').pop()}`,
      level: "info"
    })
  }, [itemMap, itemState, listsEqual, normalizeList, pushStatus])

  const handleExcludeTag = useCallback(async (itemPath: string, tagName: string) => {
    try {
      pushStatus({ message: `Excluding tag "${tagName}" from ${itemPath.split('/').pop()}` })

      const response = await EnhancedTaggingAPI.excludeTag({
        image_path: itemPath,
        tag_name: tagName
      })

      if (response.status === "success" && response.next_tag) {
        // Update the item state with the new tag from the stack
        setItemState(prev => {
          const currentState = prev[itemPath] || { selected: [], saved: false, original: [], excluded_tags: [], tag_stack: [] }
          const filteredSelected = currentState.selected.filter((name) => name !== tagName)
          return {
            ...prev,
            [itemPath]: {
              ...currentState,
              selected: filteredSelected,
              excluded_tags: [...currentState.excluded_tags, tagName],
              tag_stack: currentState.tag_stack.slice(1)
            }
          }
        })

        // Update the items to show the new tag
        setItems(prev => prev.map(item => {
          if (item.path === itemPath) {
            const newDisplayTags = item.display_tags.map((tag) =>
              tag.name === tagName ? response.next_tag! : tag
            )
            return {
              ...item,
              display_tags: newDisplayTags
            }
          }
          return item
        }))

        pushStatus({ message: `Replaced excluded tag "${tagName}" with "${response.next_tag.name}"` })
        return
      }

      // Fallback: no more tags in stack
      setItemState(prev => {
        const currentState = prev[itemPath] || { selected: [], saved: false, original: [], excluded_tags: [], tag_stack: [] }
        const filteredSelected = currentState.selected.filter((name) => name !== tagName)
        return {
          ...prev,
          [itemPath]: {
            ...currentState,
            selected: filteredSelected,
            excluded_tags: [...currentState.excluded_tags, tagName],
            tag_stack: currentState.tag_stack.slice(1)
          }
        }
      })

      setItems(prev => prev.map(item => {
        if (item.path === itemPath) {
          return {
            ...item,
            display_tags: item.display_tags.filter((tag) => tag.name !== tagName)
          }
        }
        return item
      }))

      pushStatus({ message: `Excluded tag "${tagName}"${response.status == 'success' ? " (no more tags in stack)" : ""}` })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      pushStatus({ message: `Exclude failed (${message}); removed tag locally.`, level: "error" })
      setItemState(prev => {
        const currentState = prev[itemPath] || { selected: [], saved: false, original: [], excluded_tags: [], tag_stack: [] }
        const filteredSelected = currentState.selected.filter((name) => name !== tagName)
        return {
          ...prev,
          [itemPath]: {
            ...currentState,
            selected: filteredSelected,
            excluded_tags: [...currentState.excluded_tags, tagName],
          }
        }
      })
      setItems(prev => prev.map(item => {
        if (item.path === itemPath) {
          return {
            ...item,
            display_tags: item.display_tags.filter((tag) => tag.name !== tagName)
          }
        }
        return item
      }))
    }
  }, [pushStatus])

  const handleAddUserTag = useCallback(async (itemPath: string, tagName: string) => {
    try {
      pushStatus({ message: `Adding user tag "${tagName}" to ${itemPath.split('/').pop()}` })

      const response = await EnhancedTaggingAPI.addUserTag({
        image_path: itemPath,
        tag_name: tagName
      })

      // Update the items to include the new tag
      setItems(prev => prev.map(item => {
        if (item.path === itemPath) {
          return {
            ...item,
            display_tags: [response.processed_tag, ...item.display_tags.filter(tag => tag.name !== response.processed_tag.name)]
          }
        }
        return item
      }))

      // Update the item state to include the new tag
      setItemState(prev => {
        const currentState = prev[itemPath] || { selected: [], saved: false, original: [], excluded_tags: [], tag_stack: [] }
        return {
          ...prev,
          [itemPath]: {
            ...currentState,
            selected: [...currentState.selected, response.processed_tag.name],
            saved: false
          }
        }
      })

      pushStatus({
        message: `Added user tag "${response.processed_tag.name}"${response.processed_tag.original_synonym ? ` (from "${response.processed_tag.original_synonym}")` : ""}`,
        level: "success"
      })
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      pushStatus({ message: `Add tag failed (${message}); stored locally.`, level: "error" })

      const newTag: TagCandidate = {
        name: tagName,
        score: 1.0,
        is_excluded: false,
        is_user_added: true,
      }

      setItems(prev => prev.map(item => {
        if (item.path === itemPath) {
          return {
            ...item,
            display_tags: [newTag, ...item.display_tags.filter(tag => tag.name !== newTag.name)]
          }
        }
        return item
      }))

      setItemState(prev => {
        const currentState = prev[itemPath] || { selected: [], saved: false, original: [], excluded_tags: [], tag_stack: [] }
        return {
          ...prev,
          [itemPath]: {
            ...currentState,
            selected: [...currentState.selected, tagName],
            saved: false
          }
        }
      })
    }
  }, [pushStatus])

  const visibleItems = useMemo(() => {
    const filtered = items.filter((item) => {
      const state = itemState[item.path] ?? {
        selected: normalizeList(item.selected),
        original: normalizeList(item.selected),
        saved: item.saved,
        excluded_tags: [],
        tag_stack: []
      }
      if (filters.medoidsOnly && !item.medoid) {
        return false
      }
      if (filters.unapprovedOnly) {
        if (state.saved || state.selected.length > 0) {
          return false
        }
      }
      if (filters.hideAfterSave && state.saved) {
        return false
      }
      return true
    })

    const priority = (path: string) => {
      const state = itemState[path]
      if (!state) {
        return 0
      }
      if (recentlySavedSet.has(path)) {
        return 3
      }
      if (!state.saved) {
        return 2
      }
      return 1
    }

    const sorted = [...filtered].sort((a, b) => priority(b.path) - priority(a.path))
    return sorted
  }, [filters.hideAfterSave, filters.medoidsOnly, filters.unapprovedOnly, itemState, items, normalizeList, recentlySaved])

  const handleSaveApproved = useCallback(() => {
    const entries = Object.entries(itemState)
    const toSave = entries.filter(([, state]) => state.selected.length > 0)
    const toClear = entries.filter(([path, state]) => {
      if (state.selected.length > 0) {
        return false
      }
      const original = itemMap[path]?.saved ?? false
      return original
    })

    if (toSave.length === 0 && toClear.length === 0) {
      appendWorkflowMessage("No changes detected—nothing to save.", "info")
      return
    }

    const toSavePaths = toSave.map(([path]) => path)
    setSaving(true)
    pushStatus({ message: "Saving… please wait.", level: "info" })

    void (async () => {
      try {
        await Promise.all([
          ...toSave.map(([path, state]) => saveTag({ filename: path, approved_labels: state.selected })),
          ...toClear.map(([path]) => saveTag({ filename: path, approved_labels: [] })),
        ])
        await loadGallery(true)
        setRecentlySaved(toSavePaths)
        const savedCount = toSave.length
        pushStatus({
          message: `Saved ${savedCount} image${savedCount === 1 ? "" : "s"}.`,
          level: "success",
        })
        appendWorkflowMessage(`Saved ${savedCount} image${savedCount === 1 ? "" : "s"}.`, "success")
      } catch (err) {
        const message = `Save failed: ${err instanceof Error ? err.message : String(err)}`
        pushStatus({
          message,
          level: "error",
        })
        appendWorkflowMessage(message, "error")
      } finally {
        setSaving(false)
      }
    })()
  }, [appendWorkflowMessage, itemMap, itemState, loadGallery, pushStatus])

  const handleExport = useCallback(
    (mode: "csv" | "sidecars" | "both") => {
      exportData({ mode })
        .then((response) => {
          pushStatus({
            message: `Export complete (${mode}) → ${response.files.join(", ")}`,
            level: "success",
          })
        })
        .catch((err) => {
          pushStatus({
            message: `Export failed: ${err instanceof Error ? err.message : String(err)}`,
            level: "error",
          })
        })
    },
    [pushStatus]
  )

  const handlePageSizeChange = useCallback(
    (size: number) => {
      setBlockingMessage({ title: "Updating layout…", message: `Loading ${size} images.`, tone: "warning" })
      setPageSize(size)
      pushStatus({ message: `${size} images per page`, level: "info" })
      appendWorkflowMessage(`Adjusted gallery page size to ${size} images.`, "info")
      void (async () => {
        cursorRef.current = undefined
        setCursor(undefined)
        setHasMore(true)
        setItems([])
        setItemState({})
        setSummary(null)
        await loadGallery(true)
        setBlockingMessage(null)
      })()
    },
    [appendWorkflowMessage, loadGallery, pushStatus]
  )

  const handleProcessImages = useCallback(async () => {
    if (processing) {
      return
    }
    if (!needsProcessing) {
      appendWorkflowMessage("Gallery appears up to date—running processing anyway on operator request.", "info")
    }
    setProcessing(true)
    setBlockingMessage({ title: "Processing images…", message: "Running pipeline across the selected root.", tone: "warning" })
    pushStatus({ message: "Processing images…", level: "info" })
    try {
      const response = await processImages()
      const runLabel = response.run_id ? `run ${response.run_id}` : "run"
      pushStatus({
        message: `All images processed (${runLabel})`,
        level: "success",
      })
      appendWorkflowMessage(`Processing complete (${runLabel}).`, "success")
      await loadGallery(true)
      setNeedsProcessing(false)
    } catch (err) {
      const raw = err instanceof Error ? err.message : String(err)
      const firstLine =
        raw
          .split("\n")
          .map((line) => line.trim())
          .find(
            (line) =>
              line &&
              !line.startsWith("/home") &&
              !line.includes("FutureWarning")
          ) ?? raw.split("\n")[0]
      pushStatus({
        message: `Processing failed: ${firstLine}`,
        level: "error",
      })
      appendWorkflowMessage(`Processing failed: ${firstLine}`, "error")
      setNeedsProcessing(true)
    } finally {
      setProcessing(false)
      setBlockingMessage(null)
    }
  }, [appendWorkflowMessage, loadGallery, needsProcessing, processing, pushStatus])

  return (
    <>
      <CommandBar
        filters={filters}
        onFiltersChange={setFilters}
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        onProcessImages={handleProcessImages}
        onToggleWorkflow={() => setWorkflowOpen((prev) => !prev)}
        onSaveApproved={handleSaveApproved}
        onExport={handleExport}
        processing={processing}
        needsProcessing={needsProcessing}
        saving={saving}
        stageFilter={stageFilter}
        onStageFilterChange={setStageFilter}
        summaryCounts={summary?.counts}
      />
      {saving ? (
        <BlockingOverlay
          title="Saving… please wait"
          message="We’re applying your changes to the run directory."
          tone="warning"
        />
      ) : blockingMessage ? (
        <BlockingOverlay
          title={blockingMessage.title}
          message={blockingMessage.message}
          tone={blockingMessage.tone ?? "warning"}
        />
      ) : null}
      <div className="border-b border-line/60 bg-panel px-6 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold">Enhanced Gallery</h1>
        </div>
      </div>
      <main className="mx-auto flex w-full max-w-[1920px] gap-3 px-3 py-5 lg:px-5 lg:py-6">
        {workflowOpen && !isMobile && (
          <aside className="hidden w-[300px] lg:block">
            <WorkflowSidebar
              steps={WORKFLOW_STEPS}
              className="h-[calc(100vh-190px)]"
              footerMessages={workflowMessages}
            />
          </aside>
        )}
        <div className="flex-1">
          {error && <p className="pb-4 text-sm text-destructive">{error}</p>}
          {loading && !items.length ? (
            <p className="text-sm text-muted-foreground">Loading gallery…</p>
          ) : (
            <>
              <GalleryGridEnhanced
                items={visibleItems}
                cropMode={filters.centerCrop}
                itemState={itemState}
                onToggleLabel={toggleLabelApproval}
                onExcludeTag={handleExcludeTag}
                onAddUserTag={handleAddUserTag}
              />
              {hasMore && (
                <div ref={loadMoreRef} className="flex justify-center py-4">
                  {loading ? (
                    <p className="text-sm text-muted-foreground">Loading more…</p>
                  ) : (
                    <p className="text-sm text-muted-foreground">Scroll to load more</p>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </main>
      {isMobile && (
        <Sheet open={workflowOpen} onOpenChange={setWorkflowOpen}>
          <SheetContent side="right" className="w-full max-w-sm border-line/80 bg-panel p-0">
            <SheetHeader className="border-b border-line/60 px-6 py-4">
              <SheetTitle className="text-base text-foreground">Workflow</SheetTitle>
            </SheetHeader>
            <div className="px-4 py-4">
              <WorkflowSidebar
                steps={WORKFLOW_STEPS}
                className="h-[calc(100vh-200px)] border-none bg-transparent p-0 shadow-none"
                footerMessages={workflowMessages}
              />
            </div>
          </SheetContent>
        </Sheet>
      )}
    </>
  )
}
