import { useCallback, useEffect, useMemo, useState } from "react"

import { CommandBar } from "@/components/CommandBar"
import { GalleryGrid } from "@/components/GalleryGrid"
import { WorkflowSidebar, type WorkflowStep } from "@/components/WorkflowSidebar"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import {
  exportData,
  fetchGallery,
  processImages,
  saveTag,
  type ApiGalleryItem,
  type ApiLabel,
} from "@/lib/api"
import { useStatusLog } from "@/context/status-log"
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
  const [pageSize, setPageSize] = useState(25)
  const [workflowOpen, setWorkflowOpen] = useState(false)
  const [items, setItems] = useState<ApiGalleryItem[]>([])
  const [itemState, setItemState] = useState<Record<string, ItemState>>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [processing, setProcessing] = useState(false)
  const [needsProcessing, setNeedsProcessing] = useState(true)

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

  const loadGallery = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchGallery()
      setItems(data)
      const next: Record<string, ItemState> = {}
      data.forEach((item) => {
        const normalized = normalizeList(item.selected)
        next[item.path] = {
          selected: normalized,
          original: normalized,
          saved: item.saved ?? false,
        }
      })
      setItemState(next)
      setError(null)
      const allFallback = data.length > 0 && data.every((item) => item.label_source !== "scores")
      if (allFallback) {
        pushStatus({ message: "CLIP scores not found; showing fallback tags", level: "error" })
      }
      setNeedsProcessing(allFallback)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load gallery")
    } finally {
      setLoading(false)
    }
  }, [normalizeList, pushStatus])

  useEffect(() => {
    void loadGallery()
  }, [loadGallery])

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
    return sorted.slice(0, pageSize)
  }, [filters.hideAfterSave, filters.medoidsOnly, filters.unapprovedOnly, itemState, items, normalizeList, pageSize])

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

  const handlePageSizeChange = useCallback(
    (size: number) => {
      setPageSize(size)
      pushStatus({ message: `${size} images per page`, level: "info" })
    },
    [pushStatus]
  )

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
        pageSize={pageSize}
        onPageSizeChange={handlePageSizeChange}
        onProcessImages={handleProcessImages}
        onToggleWorkflow={() => setWorkflowOpen((prev) => !prev)}
        onSaveApproved={handleSaveApproved}
        onExport={handleExport}
        processing={processing}
        needsProcessing={needsProcessing}
      />
      <main className="mx-auto flex w-full max-w-[1920px] gap-3 px-3 py-5 lg:px-5 lg:py-6">
        {workflowOpen && !isMobile && (
          <aside className="hidden w-[300px] lg:block">
            <WorkflowSidebar steps={WORKFLOW_STEPS} className="h-[calc(100vh-190px)]" />
          </aside>
        )}
        <div className="flex-1">
          {error && <p className="pb-4 text-sm text-destructive">{error}</p>}
          {loading && !items.length ? (
            <p className="text-sm text-muted-foreground">Loading gallery…</p>
          ) : (
            <GalleryGrid
              items={visibleItems}
              cropMode={filters.centerCrop}
              itemState={itemState}
              onToggleLabel={toggleLabelApproval}
            />
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
