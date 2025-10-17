import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"

export function ConfigPage() {
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-10">
      <Card className="border-line/60 bg-panel">
        <CardHeader>
          <CardTitle>Configuration Overview</CardTitle>
          <CardDescription>Future home for root paths, thresholds, and label set management.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            This page will mirror the CLI configuration fields and expose safe controls to adjust scan paths, batch sizes,
            thresholds, and export destinations. It should stay in sync with <code>config.yaml</code>.
          </p>
          <Separator className="bg-line/60" />
          <p className="text-xs">
            Placeholder only — populate once FastAPI endpoints are live and we can persist updates.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
