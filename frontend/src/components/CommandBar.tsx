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
    <section className="sticky top-14 z-40 flex h-16 items-center gap-3 border-b border-line/60 bg-panel px-5">
      {/* Primary Actions */}
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={onProcessImages}
          disabled={busy}
          variant={needsProcessing ? "destructive" : "default"}
          className="shrink-0"
        >
          {processing ? "Processing…" : saving ? "Saving…" : "Process images"}
        </Button>
        <Separator orientation="vertical" className="h-8 bg-line" />
      </div>

      {/* Filter Controls */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1 border-r border-line/40 pr-2">
          <Toggle
            pressed={filters.medoidsOnly}
            onPressedChange={handleFilterToggle("medoidsOnly")}
            className="rounded-full px-2.5 text-xs h-7 data-[state=on]:bg-blue-100 data-[state=on]:text-blue-800 data-[state=on]:border-blue-200"
            disabled={busy}
          >
            Medoids
          </Toggle>
          <Toggle
            pressed={filters.unapprovedOnly}
            onPressedChange={handleFilterToggle("unapprovedOnly")}
            className="rounded-full px-2.5 text-xs h-7 data-[state=on]:bg-orange-100 data-[state=on]:text-orange-800 data-[state=on]:border-orange-200"
            disabled={busy}
          >
            Unapproved
          </Toggle>
          <Toggle
            pressed={filters.hideAfterSave}
            onPressedChange={handleFilterToggle("hideAfterSave")}
            className="rounded-full px-2.5 text-xs h-7 data-[state=on]:bg-green-100 data-[state=on]:text-green-800 data-[state=on]:border-green-200"
            disabled={busy}
          >
            Hide saved
          </Toggle>
          <Toggle
            pressed={filters.centerCrop}
            onPressedChange={handleFilterToggle("centerCrop")}
            className="rounded-full px-2.5 text-xs h-7 data-[state=on]:bg-purple-100 data-[state=on]:text-purple-800 data-[state=on]:border-purple-200"
            disabled={busy}
          >
            Center
          </Toggle>
        </div>

        <Separator orientation="vertical" className="h-8 bg-line mx-1" />

        {/* Stage Filter */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium">Stage:</span>
          <SegmentedControl
            value={stageFilter}
            onValueChange={(value) => onStageFilterChange?.(value as ReviewStage | "all")}
            options={STAGE_OPTIONS}
            className="h-8 min-w-0"
          />
        </div>

        {/* Stage Summary Chips */}
        {(stageFilter === "all" || stageFilter === undefined) && (
          <div className="flex items-center gap-2 ml-3">
            <span className="text-xs text-muted-foreground font-medium">Summary:</span>
            <div className="flex gap-1.5">
              <span className="inline-flex items-center rounded-full bg-blue-50 border border-blue-200 px-2 py-1 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100">
                New: <span className="font-bold tabular-nums">{summaryCounts?.new ?? 0}</span>
              </span>
              <span className="inline-flex items-center rounded-full bg-yellow-50 border border-yellow-200 px-2 py-1 text-xs font-medium text-yellow-700 transition-colors hover:bg-yellow-100">
                Needs: <span className="font-bold tabular-nums">{summaryCounts?.needs_tags ?? 0}</span>
              </span>
              <span className="inline-flex items-center rounded-full bg-orange-50 border border-orange-200 px-2 py-1 text-xs font-medium text-orange-700 transition-colors hover:bg-orange-100">
                Draft: <span className="font-bold tabular-nums">{summaryCounts?.has_draft ?? 0}</span>
              </span>
              <span className="inline-flex items-center rounded-full bg-green-50 border border-green-200 px-2 py-1 text-xs font-medium text-green-700 transition-colors hover:bg-green-100">
                Saved: <span className="font-bold tabular-nums">{summaryCounts?.saved ?? 0}</span>
              </span>
              <span className="inline-flex items-center rounded-full bg-red-50 border border-red-200 px-2 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-100">
                Blocked: <span className="font-bold tabular-nums">{summaryCounts?.blocked ?? 0}</span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-2 ml-auto">
        <Button size="sm" variant="outline" onClick={onSaveApproved} disabled={busy} className="shrink-0">
          {saving ? "Saving…" : "Save approved"}
        </Button>
        <Separator orientation="vertical" className="h-8 bg-line" />
        <Button size="sm" variant="outline" onClick={onToggleWorkflow} disabled={busy} className="shrink-0">
          Workflow
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button size="sm" variant="default" disabled={busy} className="shrink-0">
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
