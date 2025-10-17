import { useMemo, useState } from "react"

import { CommandBar } from "@/components/CommandBar"
import { GalleryGrid, type GalleryItem, type GalleryLabel } from "@/components/GalleryGrid"
import { WorkflowSidebar, type WorkflowStep } from "@/components/WorkflowSidebar"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { useStatusLog } from "@/context/status-log"
import { useMediaQuery } from "@/hooks/use-media-query"

type FilterKey = "medoidsOnly" | "unapprovedOnly" | "hideAfterSave" | "centerCrop"

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

const createThumb = (seed: string) => `https://picsum.photos/seed/${encodeURIComponent(seed)}/900/700`

const MOCK_GALLERY: GalleryItem[] = Array.from({ length: 48 }, (_, index) => {
  const id = index + 1
  const filename = `IMG_${id.toString().padStart(4, "0")}.jpg`

  return {
    id: `img-${id}`,
    filename,
    thumb: createThumb(filename),
    medoid: id % 12 === 0,
    labels: [
      { name: "portrait", score: 0.91 },
      { name: "street", score: 0.72 },
      { name: "night", score: 0.54 },
      { name: "urban", score: 0.48 },
      { name: "candid", score: 0.43 },
      { name: "monochrome", score: 0.39 },
    ],
  }
})

export function GalleryPage() {
  const { push: pushStatus } = useStatusLog()
  const isMobile = useMediaQuery("(max-width: 1023px)")
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [pageSize, setPageSize] = useState(24)
  const [workflowOpen, setWorkflowOpen] = useState(false)
  const [itemState, setItemState] = useState<
    Record<
      string,
      {
        selected: string[]
        saved: boolean
      }
    >
  >({})

  const toggleLabelApproval = (itemId: string, label: GalleryLabel) => {
    setItemState((prev) => {
      const current = prev[itemId] ?? { selected: [], saved: false }
      const exists = current.selected.includes(label.name)
      const nextSelected = exists
        ? current.selected.filter((name) => name !== label.name)
        : [...current.selected, label.name]
      if (nextSelected.length === 0) {
        // remove state entry if nothing selected and nothing saved
        const { [itemId]: _omit, ...rest } = prev
        return rest
      }
      return {
        ...prev,
        [itemId]: {
          selected: nextSelected,
          saved: false,
        },
      }
    })
  }

  const visibleItems = useMemo(() => {
    let items = MOCK_GALLERY
    if (filters.medoidsOnly) {
      items = items.filter((item) => item.medoid)
    }
    if (filters.unapprovedOnly) {
      items = items.filter((item) => {
        const state = itemState[item.id]
        return !(state?.saved) && !(state?.selected.length)
      })
    }
    if (filters.hideAfterSave) {
      items = items.filter((item) => !(itemState[item.id]?.saved))
    }
    const priority = (id: string) => {
      const state = itemState[id]
      if (!state) return 0
      if (state.saved) return 2
      return 0
    }
    const sorted = [...items].sort((a, b) => priority(b.id) - priority(a.id))
    return sorted.slice(0, pageSize)
  }, [filters.medoidsOnly, filters.unapprovedOnly, filters.hideAfterSave, pageSize, itemState])

  return (
    <>
      <CommandBar
        filters={filters}
        onFiltersChange={setFilters}
        pageSize={pageSize}
        onPageSizeChange={setPageSize}
        onToggleWorkflow={() => setWorkflowOpen((prev) => !prev)}
        onSaveApproved={() => {
          const entries = Object.entries(itemState).filter(([, state]) => state.selected.length > 0)
          if (entries.length === 0) return
          const nextState: typeof itemState = {}
          entries.forEach(([itemId, state]) => {
            nextState[itemId] = {
              selected: state.selected,
              saved: true,
            }
          })
          setItemState((prev) => ({ ...prev, ...nextState }))
          const savedCount = entries.length
          pushStatus({
            message: `Saved ${savedCount} image${savedCount === 1 ? "" : "s"}.`,
            level: "success",
          })
        }}
        onExport={(mode) => {
          console.info("Export via", mode)
          pushStatus({
            message: `Export triggered (${mode})`,
            level: "info",
          })
        }}
      />
      <main className="mx-auto flex w-full max-w-[1920px] gap-3 px-3 py-5 lg:px-5 lg:py-6">
        {workflowOpen && (
          <aside className="hidden w-[300px] lg:block">
            <WorkflowSidebar steps={WORKFLOW_STEPS} className="h-[calc(100vh-190px)]" />
          </aside>
        )}
        <div className="flex-1">
          <GalleryGrid
            items={visibleItems}
            cropMode={filters.centerCrop}
            itemState={itemState}
            onToggleLabel={toggleLabelApproval}
          />
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
