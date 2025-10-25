import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

interface VirtualizedTagListProps {
  tags: Array<{
    name: string
    count: number
    frequency?: number
  }>
  selectedTags: Set<string>
  onSelectionChange: (selectedTags: Set<string>) => void
  className?: string
}

export function VirtualizedTagList({ tags, selectedTags, onSelectionChange, className }: VirtualizedTagListProps) {
  const [searchTerm, setSearchTerm] = useState("")
  const scrollContainerRef = useRef<HTMLDivElement | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(0)
  const itemHeight = 40
  const overscan = 6

  useEffect(() => {
    const node = scrollContainerRef.current
    if (!node) {
      return
    }

    const handleResize = () => {
      setContainerHeight(node.clientHeight)
    }
    handleResize()

    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(handleResize)
      observer.observe(node)
      return () => observer.disconnect()
    }

    return () => {
      /* noop */
    }
  }, [])

  const handleScroll = useCallback(() => {
    const node = scrollContainerRef.current
    if (!node) {
      return
    }
    setScrollTop(node.scrollTop)
  }, [])

  useEffect(() => {
    const node = scrollContainerRef.current
    if (node) {
      node.scrollTop = 0
    }
    setScrollTop(0)
  }, [searchTerm])

  // Filter tags based on search term
  const filteredTags = useMemo(() => {
    if (!searchTerm) return tags

    const lowerSearchTerm = searchTerm.toLowerCase()
    return tags.filter(tag =>
      tag.name.toLowerCase().includes(lowerSearchTerm)
    )
  }, [tags, searchTerm])

  // Sort tags by frequency (descending)
  const sortedTags = useMemo(() => {
    return [...filteredTags].sort((a, b) => (b.frequency || 0) - (a.frequency || 0))
  }, [filteredTags])

  const startIndex = useMemo(() => {
    return Math.max(0, Math.floor(scrollTop / itemHeight) - overscan)
  }, [scrollTop, itemHeight])

  const endIndex = useMemo(() => {
    const visibleCount = containerHeight > 0 ? Math.ceil(containerHeight / itemHeight) + overscan * 2 : sortedTags.length
    return Math.min(sortedTags.length, startIndex + visibleCount)
  }, [containerHeight, itemHeight, overscan, sortedTags.length, startIndex])

  const visibleTags = useMemo(() => sortedTags.slice(startIndex, endIndex), [sortedTags, startIndex, endIndex])

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

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2 mb-4">
        <Input
          placeholder="Search tags..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span>{filteredTags.length} tags</span>
          {selectedTags.size > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onSelectionChange(new Set())}
            >
              Clear selection
            </Button>
          )}
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        className="relative h-64 overflow-y-auto rounded-lg border border-line/40 bg-panel px-2 py-2"
        onScroll={handleScroll}
      >
        <div style={{ height: sortedTags.length * itemHeight, position: "relative" }}>
          <div
            style={{
              position: "absolute",
              top: startIndex * itemHeight,
              left: 0,
              right: 0,
            }}
            className="space-y-1.5"
          >
            {visibleTags.map((tag) => {
              const isSelected = selectedTags.has(tag.name)
              return (
                <button
                  key={tag.name}
                  type="button"
                  className={cn(
                    "flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
                    "border-line/40 bg-chip hover:border-line/60 hover:bg-panel-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary",
                    isSelected && "border-primary bg-primary text-primary-foreground"
                  )}
                  onClick={() => handleTagToggle(tag.name)}
                >
                  <span className="truncate max-w-[140px]">{tag.name}</span>
                  {tag.frequency !== undefined && (
                    <Badge variant="secondary" className="ml-1 text-xs">
                      {tag.frequency}
                    </Badge>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
