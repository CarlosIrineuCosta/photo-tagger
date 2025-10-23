import { useCallback, useState } from "react"

import { AspectRatio } from "@/components/ui/aspect-ratio"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Toggle } from "@/components/ui/toggle"
import { X } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ApiMedoidCluster } from "@/lib/api"
import type { EnhancedGalleryItem, TagCandidate } from "@/lib/enhanced_api"

type GalleryGridProps = {
  items: EnhancedGalleryItem[]
  cropMode?: boolean
  className?: string
  itemState: Record<
    string,
    {
      selected: string[]
      saved: boolean
      excluded_tags: string[]
      tag_stack: TagCandidate[]
    }
  >
  onToggleLabel: (itemPath: string, label: TagCandidate) => void
  onExcludeTag: (itemPath: string, tagName: string) => void
  onAddUserTag: (itemPath: string, tagName: string) => void
}

export function GalleryGridEnhanced({
  items,
  cropMode = false,
  className,
  itemState,
  onToggleLabel,
  onExcludeTag,
  onAddUserTag
}: GalleryGridProps) {
  const [userTagInputs, setUserTagInputs] = useState<Record<string, string>>({})
  const [showTagStack, setShowTagStack] = useState<Record<string, boolean>>({})

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

  const handleUserTagAdd = useCallback(
    (itemPath: string) => {
      const tagName = userTagInputs[itemPath]?.trim()
      if (tagName) {
        onAddUserTag(itemPath, tagName)
        setUserTagInputs(prev => ({ ...prev, [itemPath]: "" }))
      }
    },
    [userTagInputs, onAddUserTag]
  )

  const toggleTagStack = useCallback(
    (itemPath: string) => {
      setShowTagStack(prev => ({ ...prev, [itemPath]: !prev[itemPath] }))
    },
    []
  )

  const renderClusterBadge = useCallback((cluster: ApiMedoidCluster, folderName?: string) => {
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
  }, [])

  return (
    <section className={cn("rounded-2xl border border-line/60 bg-panel p-3.5", className)}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5">
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

              {/* Display Tags */}
              <div className="flex flex-wrap gap-1.5 text-xs">
                {item.display_tags.slice(0, 6).map((label) => {
                  const pressed = isLabelApproved(item.path, label.name)
                  return (
                    <div key={label.name} className="relative group">
                      <Toggle
                        pressed={pressed}
                        onPressedChange={() => onToggleLabel(item.path, label)}
                        className={cn(
                          "h-auto rounded-full border border-line/60 bg-chip px-2.5 py-1 text-[11px] font-medium tracking-tight text-foreground transition-colors pr-6",
                          "data-[state=on]:border-primary data-[state=on]:bg-primary data-[state=on]:text-foreground"
                        )}
                      >
                        <span>{label.name}</span>
                      </Toggle>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="absolute -right-1 -top-1 h-4 w-4 rounded-full p-0 opacity-0 group-hover:opacity-100 transition-opacity bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        onClick={() => onExcludeTag(item.path, label.name)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </div>
                  )
                })}
              </div>

              {/* User Tag Input */}
              <div className="flex gap-1">
                <Input
                  placeholder="Add tag..."
                  value={userTagInputs[item.path] || ""}
                  onChange={(e) => setUserTagInputs(prev => ({
                    ...prev,
                    [item.path]: e.target.value
                  }))}
                  className="h-7 text-xs"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      handleUserTagAdd(item.path)
                    }
                  }}
                />
                <Button
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => handleUserTagAdd(item.path)}
                >
                  Add
                </Button>
              </div>

              {/* Tag Stack Toggle */}
              {itemState[item.path]?.tag_stack && itemState[item.path].tag_stack.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-6 px-2 text-xs justify-start"
                  onClick={() => toggleTagStack(item.path)}
                >
                  {showTagStack[item.path] ? "Hide" : "Show"} backup tags ({itemState[item.path].tag_stack.length})
                </Button>
              )}

              {/* Tag Stack */}
              {showTagStack[item.path] && itemState[item.path]?.tag_stack && itemState[item.path].tag_stack.length > 0 && (
                <div className="border-t border-line/30 pt-2">
                  <div className="text-xs text-muted-foreground mb-1">Backup tags:</div>
                  <div className="flex flex-wrap gap-1">
                    {itemState[item.path].tag_stack.slice(0, 5).map((tag) => (
                      <Badge
                        key={tag.name}
                        variant="outline"
                        className="text-[10px] px-1.5 py-0.5"
                      >
                        {tag.name} ({tag.score.toFixed(2)})
                      </Badge>
                    ))}
                    {itemState[item.path].tag_stack.length > 5 && (
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0.5">
                        +{itemState[item.path].tag_stack.length - 5} more
                      </Badge>
                    )}
                  </div>
                </div>
              )}

              {/* Excluded Tags */}
              {itemState[item.path]?.excluded_tags && itemState[item.path].excluded_tags.length > 0 && (
                <div className="text-xs text-muted-foreground">
                  Excluded: {itemState[item.path].excluded_tags.join(", ")}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}
