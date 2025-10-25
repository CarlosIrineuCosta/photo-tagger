import { useCallback, useEffect, useMemo, useRef, useState } from "react"

import { CommandBar } from "@/components/CommandBar"
import { GalleryGrid } from "@/components/GalleryGrid"
import { NewFileBanner } from "@/components/NewFileBanner"
import { PlaceholderCard } from "@/components/PlaceholderCard"
import { WorkflowSidebar, type WorkflowStep } from "@/components/WorkflowSidebar"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import {
  exportData,
  fetchGallery,
  prefetchThumbnails,
  processImages,
  saveTag,
  type ApiGalleryItem,
  type ApiLabel,
  type ReviewStage,
  type GalleryResponse,
} from "@/lib/api"
import { useStatusLog } from "@/context/status-log"
import { useIntersectionObserver } from "@/hooks/useIntersectionObserver"
import { useMediaQuery } from "@/hooks/use-media-query"

type FilterKey = "medoidsOnly" | "unapprovedOnly" | "hideAfterSave" | "centerCrop"


type ItemState = {
  selected: string[]
  original: string[]
  saved: boolean
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
  { title: "Scores", detail: "Top labels ready", status: "active" },
  { title: "Manual review", detail: "Approve or adjust tags", status: "pending" },
  { title: "Export", detail: "CSV + XMP sidecars", status: "pending" },
]

export function GalleryPage() {
  const { push: pushStatus } = useStatusLog()
  const isMobile = useMediaQuery("(max-width: 1023px)")
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [stageFilter, setStageFilter] = useState<ReviewStage | "all">("all")
  const [workflowOpen, setWorkflowOpen] = useState(false)
  const [items, setItems] = useState<ApiGalleryItem[]>([])
  const [itemState, setItemState] = useState<Record<string, ItemState>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [needsProcessing, setNeedsProcessing] = useState(true)

  // Infinite scroll state
  const [cursor, setCursor] = useState<string | undefined>(undefined)
  const [hasMore, setHasMore] = useState(true)
  const [isPrefetching, setIsPrefetching] = useState(false)
  const [summary, setSummary] = useState<GalleryResponse["summary"] | null>(null)
  const cursorRef = useRef<string | undefined>(undefined)

  const newCount = summary?.counts?.new ?? 0

  useEffect(() => {
    cursorRef.current = cursor
  }, [cursor])

  // Ref for intersection observer
  const [loadMoreRef, isIntersecting] = useIntersectionObserver({
    threshold: 0.1,
    rootMargin: "100px",
  })

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

  const loadGallery = useCallback(
    async (reset = false) => {
      setLoading(true)
      try {
        const stageParam = stageFilter === "all" ? undefined : stageFilter
        const currentCursor = reset ? undefined : cursorRef.current
        const data = await fetchGallery(currentCursor, 50, stageParam)

        let combinedItems: ApiGalleryItem[] = []
        setItems((prev) => {
          const base = reset ? [] : prev
          combinedItems = [...base, ...data.items]
          const nextState: Record<string, ItemState> = {}
          combinedItems.forEach((item) => {
            const normalized = normalizeList(item.selected)
            nextState[item.path] = {
              selected: normalized,
              original: normalized,
              saved: item.saved ?? false,
            }
          })
          setItemState(nextState)
          return combinedItems
        })

        setSummary(data.summary)
        setCursor(data.next_cursor ?? undefined)
        setHasMore(Boolean(data.has_more))
        setError(null)

        const requiresProcessing = combinedItems.some((item) => item.requires_processing)
        setNeedsProcessing(requiresProcessing)
        if (requiresProcessing && reset) {
          pushStatus({ message: "Please run Process images again.", level: "info" })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load gallery")
      } finally {
        setLoading(false)
      }
    },
    [cursorRef, normalizeList, pushStatus, stageFilter]
  )

  useEffect(() => {
    setCursor(undefined)
    cursorRef.current = undefined
    setHasMore(true)
    setItems([])
    setItemState({})
    setSummary(null)
    void loadGallery(true)
  }, [stageFilter, loadGallery])

  useEffect(() => {
    if (isIntersecting && hasMore && !loading) {
      void loadGallery(false)
    }
  }, [isIntersecting, hasMore, loading, loadGallery])

  const itemMap = useMemo(() => {
    const map: Record<string, ApiGalleryItem> = {}
    items.forEach((item) => {
      map[item.path] = item
    })
    return map
  }, [items])

  const toggleLabelApproval = useCallback((itemPath: string, label: ApiLabel) => {
    setItemState((prev) => {
      const persisted = itemMap[itemPath]
      const current = prev[itemPath] ?? {
        selected: normalizeList(persisted?.selected),
        original: normalizeList(persisted?.selected),
        saved: persisted?.saved ?? false,
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
        },
      }
    })
  }, [itemMap, listsEqual, normalizeList])

  const visibleItems = useMemo(() => {
    const filtered = items.filter((item) => {
      const state = itemState[item.path] ?? {
        selected: normalizeList(item.selected),
        original: normalizeList(item.selected),
        saved: item.saved,
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
      return state.saved ? 1 : 0
    }

    const sorted = [...filtered].sort((a, b) => priority(b.path) - priority(a.path))
    return sorted
  }, [filters.hideAfterSave, filters.medoidsOnly, filters.unapprovedOnly, itemState, items, normalizeList])

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
      pushStatus({ message: "No selections to save.", level: "info" })
      return
    }

    Promise.all([
      ...toSave.map(([path, state]) => saveTag({ filename: path, approved_labels: state.selected })),
      ...toClear.map(([path]) => saveTag({ filename: path, approved_labels: [] })),
    ])
      .then(async () => {
        await loadGallery()
        const savedCount = toSave.length
        pushStatus({
          message: `Saved ${savedCount} image${savedCount === 1 ? "" : "s"}.`,
          level: "success",
        })
      })
      .catch((err) => {
        pushStatus({
          message: `Save failed: ${err instanceof Error ? err.message : String(err)}`,
          level: "error",
        })
      })
  }, [itemMap, itemState, loadGallery, pushStatus])

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

  const handlePrefetchThumbnails = useCallback(async () => {
    if (isPrefetching) {
      return
    }
    setIsPrefetching(true)
    try {
      const response = await prefetchThumbnails()
      pushStatus({
        message: `Thumbnail prefetch queued for ${response.scheduled} file${response.scheduled === 1 ? "" : "s"}.`,
        level: response.scheduled ? "success" : "info",
      })
    } catch (err) {
      pushStatus({
        message: `Prefetch failed: ${err instanceof Error ? err.message : String(err)}`,
        level: "error",
      })
    } finally {
      setIsPrefetching(false)
    }
  }, [isPrefetching, pushStatus])


  const handleProcessImages = useCallback(async () => {
    if (processing) {
      return
    }
    setProcessing(true)
    pushStatus({ message: "Processing images…", level: "info" })
    try {
      const response = await processImages()
      const runLabel = response.run_id ? `run ${response.run_id}` : "run"
      pushStatus({
        message: `All images processed (${runLabel})`,
        level: "success",
      })
      await loadGallery()
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
      setNeedsProcessing(true)
    } finally {
      setProcessing(false)
    }
  }, [loadGallery, processing, pushStatus])

  return (
    <>
      <CommandBar
        filters={filters}
        onFiltersChange={setFilters}
        onProcessImages={handleProcessImages}
        onToggleWorkflow={() => setWorkflowOpen((prev) => !prev)}
        onSaveApproved={handleSaveApproved}
        onExport={handleExport}
        processing={processing}
        needsProcessing={needsProcessing}
        stageFilter={stageFilter}
        onStageFilterChange={(value) => {
          setStageFilter(value)
          pushStatus({ message: `Filter: ${value}`, level: "info" })
        }}
      />
      <main className="mx-auto flex w-full max-w-[1920px] gap-3 px-3 py-5 lg:px-5 lg:py-6">
        {workflowOpen && !isMobile && (
          <aside className="hidden w-[300px] lg:block">
            <WorkflowSidebar steps={WORKFLOW_STEPS} className="h-[calc(100vh-190px)]" />
          </aside>
        )}
        <div className="flex-1">
          {error && <p className="pb-4 text-sm text-destructive">{error}</p>}
          <NewFileBanner
            newCount={newCount}
            onPrefetchThumbnails={handlePrefetchThumbnails}
            isPrefetching={isPrefetching}
          />
          {loading && !items.length ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
              {Array.from({ length: 12 }).map((_, index) => (
                <PlaceholderCard key={index} className="h-[220px]" />
              ))}
            </div>
          ) : (
            <>
              <GalleryGrid
                items={visibleItems}
                cropMode={filters.centerCrop}
                itemState={itemState}
                onToggleLabel={toggleLabelApproval}
              />
              {loading && items.length > 0 && (
                <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
                  {Array.from({ length: 6 }).map((_, index) => (
                    <PlaceholderCard key={`placeholder-${index}`} className="h-[220px]" />
                  ))}
                </div>
              )}
              {/* Load more trigger for infinite scroll */}
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
              <WorkflowSidebar steps={WORKFLOW_STEPS} className="h-[calc(100vh-200px)] border-none bg-transparent p-0 shadow-none" />
            </div>
          </SheetContent>
        </Sheet>
      )}
    </>
  )
}
