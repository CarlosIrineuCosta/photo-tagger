import { useCallback } from "react"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Toggle } from "@/components/ui/toggle"
import { cn } from "@/lib/utils"
import type { ApiGalleryItem, ApiLabel, ApiMedoidCluster } from "@/lib/api"

type GalleryGridProps = {
  items: ApiGalleryItem[]
  cropMode?: boolean
  className?: string
  itemState: Record<
    string,
    {
      selected: string[]
      saved: boolean
    }
  >
  onToggleLabel: (itemPath: string, label: ApiLabel) => void
}

export function GalleryGrid({ items, cropMode = false, className, itemState, onToggleLabel }: GalleryGridProps) {
  const fallbackThumb =
    "data:image/svg+xml;charset=UTF-8," +
    encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='512' height='512'><rect width='512' height='512' fill='#1C2F47'/><text x='50%' y='50%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, sans-serif' font-size='28' fill='#BDC6D5'>Preview unavailable</text></svg>"
    )

  const isLabelApproved = useCallback(
    (itemPath: string, labelName: string) => {
      const selected = itemState[itemPath]?.selected ?? []
      return selected.includes(labelName)
    },
    [itemState]
  )

  const renderClusterBadge = useCallback(
    (cluster: ApiMedoidCluster, folderName?: string) => {
      const parts: string[] = []
      if (cluster.cluster_type === "tag") {
        parts.push(cluster.cluster_tag || cluster.label_hint || "Tag cluster")
      } else if (cluster.cluster_type === "embedding") {
        parts.push(cluster.label_hint || "Embedding cluster")
      } else {
        parts.push(folderName ? `Folder · ${folderName}` : "Folder medoid")
      }
      if (cluster.cluster_size) {
        parts.push(`n=${cluster.cluster_size}`)
      }
      if (cluster.cosine_to_centroid) {
        parts.push(`cos=${cluster.cosine_to_centroid.toFixed(2)}`)
      }
      return parts.join(" · ")
    },
    []
  )

  return (
    <section className={cn("rounded-2xl border border-line/60 bg-panel p-3.5", className)}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 2xl:grid-cols-6">
        {items.map((item) => (
          <Card key={item.id ?? item.path} className="overflow-hidden border-line/60 bg-panel-2">
            <div className="relative">
              <AspectRatio ratio={1}>
                <img
                  src={item.thumb}
                  alt={item.filename}
                  onError={(event) => {
                    const target = event.currentTarget
                    if (target.src !== fallbackThumb) {
                      target.src = fallbackThumb
                    }
                  }}
                  className={cn("h-full w-full rounded-none object-contain", cropMode && "object-cover")}
                  loading="lazy"
                />
              </AspectRatio>
              <div className="pointer-events-none absolute inset-x-3 top-3 flex items-center justify-between">
                {item.medoid && (
                  <Badge variant="outline" className="border-line bg-panel/80 text-[11px] uppercase">
                    Medoid
                  </Badge>
                )}
                {(() => {
                  const state = itemState[item.path]
                  if (!state || state.selected.length === 0) return null
                  if (state.saved) {
                    return (
                      <Badge variant="success" className="text-[11px] uppercase tracking-wide">
                        Saved
                      </Badge>
                    )
                  }
                  return (
                    <Badge variant="secondary" className="text-[11px] uppercase tracking-wide">
                      Selected
                    </Badge>
                  )
                })()}
              </div>
            </div>
            <CardContent className="flex flex-1 flex-col gap-2.5 p-3">
              <div className="truncate text-xs text-muted-foreground">{item.filename}</div>
              {item.medoid && item.medoid_clusters && item.medoid_clusters.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {item.medoid_clusters.slice(0, 3).map((cluster, index) => (
                    <Badge key={`${cluster.cluster_type}-${cluster.label_hint}-${index}`} variant="outline" className="text-[10px] uppercase">
                      {renderClusterBadge(cluster, item.medoid_folder)}
                    </Badge>
                  ))}
                  {item.medoid_clusters.length > 3 ? (
                    <Badge variant="outline" className="text-[10px] uppercase">
                      +{item.medoid_clusters.length - 3} more
                    </Badge>
                  ) : null}
                </div>
              ) : null}
              <div className="flex flex-wrap gap-1.5 text-xs">
                {item.labels.slice(0, 6).map((label) => {
                  const pressed = isLabelApproved(item.path, label.name)
                  return (
                    <Toggle
                      key={label.name}
                      pressed={pressed}
                      onPressedChange={() => onToggleLabel(item.path, label)}
                      className={cn(
                        "h-auto rounded-full border border-line/60 bg-chip px-2.5 py-1 text-[11px] font-medium tracking-tight text-foreground transition-colors",
                        "data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-foreground"
                      )}
                    >
                      <span>{label.name}</span>
                    </Toggle>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
