import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export type WorkflowStep = {
  title: string
  detail?: string
  status?: "done" | "active" | "pending"
}

type WorkflowSidebarProps = {
  steps: WorkflowStep[]
  className?: string
}

export function WorkflowSidebar({ steps, className }: WorkflowSidebarProps) {
  return (
    <Card className={cn("flex h-full flex-col border-line/60 bg-panel p-4", className)}>
      <CardHeader className="pb-4">
        <CardTitle className="text-base">Workflow</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-full pr-2">
          <ol className="space-y-3">
            {steps.map((step) => (
              <li
                key={step.title}
                className={cn(
                  "rounded-lg border border-line/60 bg-panel-2 px-4 py-3 text-sm",
                  step.status === "done" && "border-success/40",
                  step.status === "active" && "border-primary/40"
                )}
              >
                <div className="font-medium leading-tight">{step.title}</div>
                {step.detail && <div className="mt-1 text-xs text-muted-foreground">{step.detail}</div>}
              </li>
            ))}
          </ol>
        </ScrollArea>
      </CardContent>
    </Card>
  )
}
