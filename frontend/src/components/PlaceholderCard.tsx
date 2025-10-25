import { Loader2 } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface PlaceholderCardProps {
  className?: string
}

export function PlaceholderCard({ className }: PlaceholderCardProps) {
  return (
    <Card className={cn("overflow-hidden border-line/60 bg-panel-2", className)}>
      <CardContent className="flex flex-col items-center justify-center h-full p-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="mt-2 text-sm text-muted-foreground">Loading thumbnail...</p>
      </CardContent>
    </Card>
  )
}
