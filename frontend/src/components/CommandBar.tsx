import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { SegmentedControl } from "@/components/ui/segmented-control"
import { Toggle } from "@/components/ui/toggle"
import type { ReviewStage } from "@/lib/api"

type FilterKey = "medoidsOnly" | "unapprovedOnly" | "hideAfterSave" | "centerCrop"

type CommandBarProps = {
  filters: Record<FilterKey, boolean>
  onFiltersChange: (next: Record<FilterKey, boolean>) => void
  onProcessImages?: () => void
  onExport?: (mode: "csv" | "sidecars" | "both") => void
  onToggleWorkflow?: () => void
  onSaveApproved?: () => void
  processing?: boolean
  needsProcessing?: boolean
  saving?: boolean
  stageFilter?: ReviewStage | "all"
  onStageFilterChange?: (value: ReviewStage | "all") => void
  summaryCounts?: Record<string, number>
}


const STAGE_OPTIONS: Array<{ value: ReviewStage | "all"; label: string }> = [
  { value: "all", label: "All" },
  { value: "new", label: "New" },
  { value: "needs_tags", label: "Needs tags" },
  { value: "has_draft", label: "Draft" },
  { value: "saved", label: "Saved" },
  { value: "blocked", label: "Blocked" },
]

export function CommandBar({
  filters,
  onFiltersChange,
  onProcessImages,
  onExport,
  onToggleWorkflow,
  onSaveApproved,
  processing = false,
  needsProcessing = false,
  saving = false,
  stageFilter = "all",
  onStageFilterChange,
  summaryCounts,
}: CommandBarProps) {
  const handleFilterToggle = (key: FilterKey) => (pressed: boolean) => {
    onFiltersChange({ ...filters, [key]: pressed })
  }

  const busy = processing || saving

  return (
    <section className="sticky top-14 z-40 flex h-16 items-center gap-2.5 border-b border-line/60 bg-panel px-5">
      <Button
        size="sm"
        onClick={onProcessImages}
        disabled={busy}
        variant={needsProcessing ? "destructive" : "default"}
      >
        {processing ? "Processing…" : saving ? "Saving…" : "Process images"}
      </Button>
      <Separator orientation="vertical" className="h-8 bg-line" />
      <Toggle
        pressed={filters.medoidsOnly}
        onPressedChange={handleFilterToggle("medoidsOnly")}
        className="rounded-full px-3 text-xs"
        disabled={busy}
      >
        Medoids only
      </Toggle>
      <Toggle
        pressed={filters.unapprovedOnly}
        onPressedChange={handleFilterToggle("unapprovedOnly")}
        className="rounded-full px-3 text-xs"
        disabled={busy}
      >
        Only unapproved
      </Toggle>
      <Toggle
        pressed={filters.hideAfterSave}
        onPressedChange={handleFilterToggle("hideAfterSave")}
        className="rounded-full px-3 text-xs"
        disabled={busy}
      >
        Hide saved
      </Toggle>
      <Toggle
        pressed={filters.centerCrop}
        onPressedChange={handleFilterToggle("centerCrop")}
        className="rounded-full px-3 text-xs"
        disabled={busy}
      >
        Center-crop
      </Toggle>
      <Separator orientation="vertical" className="h-8 bg-line" />

      {/* Stage Filter */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">Stage:</span>
        <SegmentedControl
          value={stageFilter}
          onValueChange={(value) => onStageFilterChange?.(value as ReviewStage | "all")}
          options={STAGE_OPTIONS}
          className="h-8"
        />
      </div>

      {/* Stage Summary Chips */}
      {(stageFilter === "all" || stageFilter === undefined) && (
        <div className="flex items-center gap-2 ml-4">
          <span className="text-xs text-muted-foreground">Summary:</span>
          <div className="flex gap-1">
            <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-1 text-xs font-medium text-blue-800">
              New: <span className="font-bold">{summaryCounts?.new ?? 0}</span>
            </span>
            <span className="inline-flex items-center rounded-full bg-yellow-100 px-2 py-1 text-xs font-medium text-yellow-800">
              Needs Tags: <span className="font-bold">{summaryCounts?.needs_tags ?? 0}</span>
            </span>
            <span className="inline-flex items-center rounded-full bg-orange-100 px-2 py-1 text-xs font-medium text-orange-800">
              Draft: <span className="font-bold">{summaryCounts?.has_draft ?? 0}</span>
            </span>
            <span className="inline-flex items-center rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-800">
              Saved: <span className="font-bold">{summaryCounts?.saved ?? 0}</span>
            </span>
            <span className="inline-flex items-center rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-800">
              Blocked: <span className="font-bold">{summaryCounts?.blocked ?? 0}</span>
            </span>
          </div>
        </div>
      )}

      <Separator orientation="vertical" className="h-8 bg-line" />
      <Button size="sm" variant="outline" onClick={onSaveApproved} disabled={busy}>
        {saving ? "Saving…" : "Save approved"}
      </Button>
      <Separator orientation="vertical" className="ml-1 h-8 bg-line" />

      <div className="ml-auto flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={onToggleWorkflow} disabled={busy}>
          Workflow
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="default" disabled={busy}>
              Export ▾
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-40">
            <DropdownMenuItem onSelect={() => onExport?.("csv")}>CSV</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onExport?.("sidecars")}>Sidecars</DropdownMenuItem>
            <DropdownMenuItem onSelect={() => onExport?.("both")}>Both</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </section>
  )
}
