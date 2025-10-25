import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface VirtualizedPillTagListProps {
  tags: Array<{
    name: string
    count: number
    frequency?: number
    occurrences?: number
  }>
  selectedTags: Set<string>
  onSelectionChange: (selectedTags: Set<string>) => void
  className?: string
  showFrequency?: boolean
  enableDragDrop?: boolean
  onBatchAction?: (action: string, tags: string[]) => void
}

interface DragItem {
  tag: string
  index: number
}

export function VirtualizedPillTagList({
  tags,
  selectedTags,
  onSelectionChange,
  className,
  showFrequency = true,
  enableDragDrop = false,
  onBatchAction
}: VirtualizedPillTagListProps) {
  const [searchTerm, setSearchTerm] = useState("")
  const [draggedItem, setDraggedItem] = useState<DragItem | null>(null)
  const [dragOverBin, setDragOverBin] = useState<string | null>(null)
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)
  const itemHeight = 48
  const overscan = 8

  useEffect(() => {
    const node = scrollContainerRef.current
    if (!node) return

    const handleResize = () => {
      setContainerHeight(node.clientHeight)
    }
    handleResize()

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(handleResize)
      observer.observe(node)
      return () => observer.disconnect()
    }
  }, [])

  const handleScroll = useCallback(() => {
    const node = scrollContainerRef.current
    if (!node) return
    setScrollTop(node.scrollTop)
  }, [])

  useEffect(() => {
    const node = scrollContainerRef.current
    if (node) {
      node.scrollTop = 0
    }
    setScrollTop(0)
  }, [searchTerm])

  // Filter and sort tags
  const processedTags = useMemo(() => {
    let filtered = tags
    if (searchTerm) {
      const lowerSearchTerm = searchTerm.toLowerCase()
      filtered = tags.filter(tag =>
        tag.name.toLowerCase().includes(lowerSearchTerm)
      )
    }

    // Sort by frequency (descending) then by name
    return [...filtered].sort((a, b) => {
      const freqA = a.frequency || a.occurrences || 0
      const freqB = b.frequency || b.occurrences || 0
      if (freqB !== freqA) {
        return freqB - freqA
      }
      return a.name.localeCompare(b.name)
    })
  }, [tags, searchTerm])

  const startIndex = useMemo(() => {
    return Math.max(0, Math.floor(scrollTop / itemHeight) - overscan)
  }, [scrollTop, itemHeight])

  const endIndex = useMemo(() => {
    const visibleCount = containerHeight > 0 ? Math.ceil(containerHeight / itemHeight) + overscan * 2 : processedTags.length
    return Math.min(processedTags.length, startIndex + visibleCount)
  }, [containerHeight, itemHeight, overscan, processedTags.length, startIndex])

  const visibleTags = useMemo(() => processedTags.slice(startIndex, endIndex), [processedTags, startIndex, endIndex])

  const handleTagToggle = useCallback(
    (tagName: string) => {
      const next = new Set(selectedTags)
      if (next.has(tagName)) {
        next.delete(tagName)
      } else {
        next.add(tagName)
      }
      onSelectionChange(next)
    },
    [onSelectionChange, selectedTags]
  )

  const handleDragStart = useCallback((e: React.DragEvent, tag: string, index: number) => {
    if (!enableDragDrop) return
    setDraggedItem({ tag, index })
    e.dataTransfer.effectAllowed = 'move'
  }, [enableDragDrop])

  const handleDragEnd = useCallback(() => {
    setDraggedItem(null)
    setDragOverBin(null)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    if (!enableDragDrop) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
  }, [enableDragDrop])

  const handleBinDragOver = useCallback((bin: string) => {
    if (!enableDragDrop) return
    setDragOverBin(bin)
  }, [enableDragDrop])

  const handleBinDrop = useCallback((e: React.DragEvent, action: string) => {
    if (!enableDragDrop || !draggedItem || !onBatchAction) return
    e.preventDefault()

    const selectedTagsArray = Array.from(selectedTags)
    if (selectedTagsArray.length === 0) {
      selectedTagsArray.push(draggedItem.tag)
    }

    onBatchAction(action, selectedTagsArray)
    setDraggedItem(null)
    setDragOverBin(null)
  }, [enableDragDrop, draggedItem, selectedTags, onBatchAction])

  const getFrequencyDisplay = useCallback((tag: typeof tags[0]) => {
    const freq = tag.frequency || tag.occurrences || 0
    if (freq >= 1000) {
      return `${(freq / 1000).toFixed(1)}k`
    }
    return freq.toString()
  }, [])

  return (
    <div className={cn("space-y-4", className)}>
      {/* Search and controls */}
      <div className="flex items-center gap-3">
        <Input
          placeholder="Search tags..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{processedTags.length} tags</span>
          {selectedTags.size > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelectionChange(new Set())}
            >
              Clear selection ({selectedTags.size})
            </Button>
          )}
        </div>
      </div>

      {/* Batch action bins */}
      {enableDragDrop && onBatchAction && (
        <div className="flex gap-3 p-3 bg-panel-2/50 rounded-lg border border-line/30">
          <Card
            className={cn(
              "flex-1 p-3 cursor-pointer transition-colors",
              dragOverBin === "promote" && "border-primary bg-primary/5"
            )}
            onDragOver={handleDragOver}
            onDragEnter={() => handleBinDragOver("promote")}
            onDragLeave={() => handleBinDragOver("")}
            onDrop={(e) => handleBinDrop(e, "promote")}
          >
            <CardContent className="p-0 text-center">
              <div className="text-sm font-medium text-foreground">Promote</div>
              <div className="text-xs text-muted-foreground">Move to structured groups</div>
            </CardContent>
          </Card>

          <Card
            className={cn(
              "flex-1 p-3 cursor-pointer transition-colors",
              dragOverBin === "exclude" && "border-destructive bg-destructive/5"
            )}
            onDragOver={handleDragOver}
            onDragEnter={() => handleBinDragOver("exclude")}
            onDragLeave={() => handleBinDragOver("")}
            onDrop={(e) => handleBinDrop(e, "exclude")}
          >
            <CardContent className="p-0 text-center">
              <div className="text-sm font-medium text-foreground">Exclude</div>
              <div className="text-xs text-muted-foreground">Remove from suggestions</div>
            </CardContent>
          </Card>

          <Card
            className={cn(
              "flex-1 p-3 cursor-pointer transition-colors",
              dragOverBin === "review" && "border-warning bg-warning/5"
            )}
            onDragOver={handleDragOver}
            onDragEnter={() => handleBinDragOver("review")}
            onDragLeave={() => handleBinDragOver("")}
            onDrop={(e) => handleBinDrop(e, "review")}
          >
            <CardContent className="p-0 text-center">
              <div className="text-sm font-medium text-foreground">Review</div>
              <div className="text-xs text-muted-foreground">Mark for later review</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Virtualized pill list */}
      <div
        ref={scrollContainerRef}
        className="relative overflow-y-auto rounded-lg border border-line/40 bg-panel px-3 py-2"
        style={{ height: '400px' }}
        onScroll={handleScroll}
      >
        <div style={{ height: processedTags.length * itemHeight, position: "relative" }}>
          <div
            style={{
              position: "absolute",
              top: startIndex * itemHeight,
              left: 0,
              right: 0,
              height: (endIndex - startIndex) * itemHeight,
            }}
            className="flex flex-col gap-1.5 p-1"
          >
            {visibleTags.map((tag, index) => {
              const actualIndex = startIndex + index
              const isSelected = selectedTags.has(tag.name)
              const isDragging = draggedItem?.tag === tag.name

              return (
                <div
                  key={tag.name}
                  className={cn(
                    "flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-all cursor-pointer",
                    "border-line/40 bg-chip hover:border-line/60 hover:bg-panel-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary",
                    isSelected && "border-primary bg-primary text-primary-foreground shadow-sm",
                    isDragging && "opacity-50 scale-95",
                    enableDragDrop && "cursor-move"
                  )}
                  onClick={() => handleTagToggle(tag.name)}
                  draggable={enableDragDrop}
                  onDragStart={(e) => handleDragStart(e, tag.name, actualIndex)}
                  onDragEnd={handleDragEnd}
                  style={{ height: itemHeight - 6 }}
                >
                  <span className="truncate flex-1 text-left">{tag.name}</span>
                  {showFrequency && (
                    <Badge
                      variant={isSelected ? "secondary" : "outline"}
                      className="ml-1 text-xs shrink-0"
                    >
                      {getFrequencyDisplay(tag)}
                    </Badge>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
