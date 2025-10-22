import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Separator } from "@/components/ui/separator"
import { Toggle } from "@/components/ui/toggle"
import { cn } from "@/lib/utils"

type FilterKey = "medoidsOnly" | "unapprovedOnly" | "hideAfterSave" | "centerCrop"

type CommandBarProps = {
  filters: Record<FilterKey, boolean>
  onFiltersChange: (next: Record<FilterKey, boolean>) => void
  pageSize?: number
  onPageSizeChange?: (size: number) => void
  onProcessImages?: () => void
  onExport?: (mode: "csv" | "sidecars" | "both") => void
  onToggleWorkflow?: () => void
  onSaveApproved?: () => void
  processing?: boolean
  needsProcessing?: boolean
  saving?: boolean
}

const PAGE_SIZES = [25, 50, 100]

export function CommandBar({
  filters,
  onFiltersChange,
  onPageSizeChange,
  onProcessImages,
  onExport,
  pageSize = PAGE_SIZES[0],
  onToggleWorkflow,
  onSaveApproved,
  processing = false,
  needsProcessing = false,
  saving = false,
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
      <Button size="sm" variant="outline" onClick={onSaveApproved} disabled={busy}>
        {saving ? "Saving…" : "Save approved"}
      </Button>
      <Separator orientation="vertical" className="ml-1 h-8 bg-line" />
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span>Page size:</span>
        <div className="flex gap-2">
          {PAGE_SIZES.map((size) => (
            <Button
              key={size}
              variant="ghost"
              size="sm"
              className={cn("h-8 px-3 text-xs", pageSize === size && "bg-panel-2 text-foreground")}
              onClick={() => onPageSizeChange?.(size)}
              disabled={busy}
            >
              {size}
            </Button>
          ))}
        </div>
      </div>
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
