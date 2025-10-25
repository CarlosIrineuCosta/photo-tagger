import { AlertCircle, Download, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription } from "@/components/ui/alert"

interface NewFileBannerProps {
  newCount: number
  onPrefetchThumbnails?: () => void
  isPrefetching?: boolean
}

export function NewFileBanner({ newCount, onPrefetchThumbnails, isPrefetching = false }: NewFileBannerProps) {
  if (newCount === 0) return null

  return (
    <Alert className="mb-4 border-blue-200 bg-blue-50/50">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex items-center justify-between">
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
          {isPrefetching && (
            <div className="flex items-center text-sm text-muted-foreground">
              <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
              Prefetching...
            </div>
          )}
        </div>
      </AlertDescription>
    </Alert>
  )
}
