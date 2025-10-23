import { useCallback, useEffect, useMemo, useState } from "react"

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
} from "@/lib/api"
import EnhancedTaggingAPI, { type EnhancedGalleryItem, type TagCandidate } from "@/lib/enhanced_api"
import { useStatusLog } from "@/context/status-log"
import { useMediaQuery } from "@/hooks/use-media-query"

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

  const loadGallery = useCallback(async () => {
    setLoading(true)
    setBlockingMessage({ title: "Loading gallery…", message: "Fetching latest tags and thumbnails.", tone: "warning" })
    try {
      const data = await fetchGallery()

      pushStatus({ message: "Processing tags with enhanced system..." })
      try {
        const enhancedItems = await EnhancedTaggingAPI.enhanceGalleryItems(data)
        setItems(enhancedItems)

        const next: Record<string, ItemState> = {}
        enhancedItems.forEach((item) => {
          const normalized = normalizeList(item.selected)
          next[item.path] = {
            selected: normalized,
            original: normalized,
            saved: item.saved ?? false,
            excluded_tags: item.excluded_tags || [],
            tag_stack: item.tag_stack || []
          }
        })
        setItemState(next)
        pushStatus({ message: `Enhanced processing complete for ${enhancedItems.length} images`, level: "success" })
        appendWorkflowMessage(`Enhanced processing complete for ${enhancedItems.length} images.`, "success")
      } catch (err) {
        console.error("Enhanced processing failed:", err)
        pushStatus({ message: "Enhanced processing failed; using baseline tags.", level: "error" })
        appendWorkflowMessage("Enhanced processing failed; using baseline tags.", "warning")
        const converted = convertToEnhancedItems(data)
        setItems(converted)
        const fallbackState: Record<string, ItemState> = {}
        converted.forEach((item) => {
          const normalized = normalizeList(item.selected)
          fallbackState[item.path] = {
            selected: normalized,
            original: normalized,
            saved: item.saved ?? false,
            excluded_tags: [],
            tag_stack: []
          }
        })
        setItemState(fallbackState)
      }

      setError(null)
      const allFallback = data.length > 0 && data.every((item) => item.label_source !== "scores")
      if (allFallback) {
        pushStatus({ message: "CLIP scores not found; showing fallback tags", level: "error" })
        appendWorkflowMessage("CLIP scores missing; showing fallback tags.", "warning")
      }
      setNeedsProcessing(allFallback)
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load gallery"
      setError(message)
      appendWorkflowMessage(`Gallery load failed: ${message}`, "error")
    } finally {
      setLoading(false)
      setBlockingMessage(null)
    }
  }, [appendWorkflowMessage, convertToEnhancedItems, normalizeList, pushStatus])

  useEffect(() => {
    void loadGallery()
  }, [loadGallery])

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
    return sorted.slice(0, pageSize)
  }, [filters.hideAfterSave, filters.medoidsOnly, filters.unapprovedOnly, itemState, items, normalizeList, pageSize, recentlySaved])

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
        await loadGallery()
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
        await loadGallery()
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
      appendWorkflowMessage("Gallery is already up to date—no processing required.", "info")
      return
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
            <GalleryGridEnhanced
              items={visibleItems}
              cropMode={filters.centerCrop}
              itemState={itemState}
              onToggleLabel={toggleLabelApproval}
              onExcludeTag={handleExcludeTag}
              onAddUserTag={handleAddUserTag}
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
