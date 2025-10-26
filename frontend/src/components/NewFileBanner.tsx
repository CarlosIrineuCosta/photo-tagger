import { AlertCircle, CheckCircle, Download, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface NewFileBannerProps {
  newCount: number
  onPrefetchThumbnails?: () => void
  isPrefetching?: boolean
  prefetchProgress?: { processed: number; total: number } | null
  prefetchJobId?: string | null
}

export function NewFileBanner({
  newCount,
  onPrefetchThumbnails,
  isPrefetching = false,
  prefetchProgress = null,
  prefetchJobId = null
}: NewFileBannerProps) {
  if (newCount === 0) return null

  const progressPercent = prefetchProgress && prefetchProgress.total > 0
    ? Math.round((prefetchProgress.processed / prefetchProgress.total) * 100)
    : prefetchProgress && prefetchProgress.total === 0
      ? 100
      : 0

  const getPrefetchStatusIcon = () => {
    if (!isPrefetching) return null
    if (progressPercent === 100) return <CheckCircle className="h-3 w-3 text-green-500" />
    return <RefreshCw className="h-3 w-3 animate-spin text-blue-500" />
  }

  const getPrefetchStatusText = () => {
    if (!isPrefetching) return null
    if (prefetchProgress) {
      return `${prefetchProgress.processed}/${prefetchProgress.total} files (${progressPercent}%)`
    }
    return "Initializing..."
  }

  return (
    <Alert className={cn(
      "mb-4",
      isPrefetching
        ? progressPercent === 100
          ? "border-green-200 bg-green-50/50"
          : "border-blue-200 bg-blue-50/50"
        : "border-blue-200 bg-blue-50/50"
    )}>
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-medium">{newCount} new file{newCount === 1 ? "" : "s"} detected</span>
            <span className="text-sm text-muted-foreground ml-2">
              Prefetch thumbnails to warm the cache before review.
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onPrefetchThumbnails}
              disabled={isPrefetching}
              className="h-8"
            >
              <Download className="h-3 w-3 mr-1" />
              Prefetch thumbnails
            </Button>
          </div>
        </div>

        {isPrefetching && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                {getPrefetchStatusIcon()}
                <span className="text-muted-foreground">
                  {getPrefetchStatusText()}
                </span>
                {prefetchJobId && (
                  <Badge variant="outline" className="text-xs">
                    Job: {prefetchJobId}
                  </Badge>
                )}
              </div>
            </div>

            {prefetchProgress && (
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300 ease-in-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            )}

            <div className="text-xs text-muted-foreground">
              {progressPercent === 100
                ? "Prefetch completed! Thumbnails should now load faster."
                : "Processing thumbnails in the background. Gallery remains fully functional."
              }
            </div>
          </div>
        )}
      </AlertDescription>
    </Alert>
  )
}
