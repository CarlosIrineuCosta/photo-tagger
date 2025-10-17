import { Badge, type BadgeProps } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

export type StatusEntry = {
  id: string
  message: string
  level?: "info" | "success" | "error"
  timestamp?: string
}

type StatusStripProps = {
  items: StatusEntry[]
  className?: string
}

const LEVEL_TO_VARIANT: Record<NonNullable<StatusEntry["level"]>, BadgeProps["variant"]> = {
  info: "outline",
  success: "success",
  error: "destructive",
}

export function StatusStrip({ items, className }: StatusStripProps) {
  return (
    <footer
      className={cn(
        "fixed bottom-3 left-3 right-3 z-40 flex items-center gap-3 rounded-lg border border-line/75 bg-panel/80 px-4 py-2 text-xs text-muted-foreground backdrop-blur-md",
        className
      )}
    >
      <span className="text-muted-foreground">Recent activity</span>
      <div className="flex flex-1 items-center gap-2 overflow-hidden">
        {items.slice(-20).map((entry) => (
          <div key={entry.id} className="flex shrink-0 items-center gap-2 rounded-md border border-line/60 bg-panel-2 px-3 py-1">
            {entry.level && (
              <Badge variant={LEVEL_TO_VARIANT[entry.level]} className="text-[10px] uppercase tracking-wide">
                {entry.level}
              </Badge>
            )}
            <span className="max-w-xs truncate text-foreground/90">{entry.message}</span>
            {entry.timestamp && <span className="text-muted-foreground">{entry.timestamp}</span>}
          </div>
        ))}
      </div>
    </footer>
  )
}
