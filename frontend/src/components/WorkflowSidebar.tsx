import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { cn } from "@/lib/utils"

export type WorkflowStep = {
  title: string
  detail?: string
  status?: "done" | "active" | "pending"
}

export type WorkflowMessage = {
  id: string
  text: string
  tone?: "info" | "success" | "warning" | "error"
  timestamp?: string
}

type WorkflowSidebarProps = {
  steps: WorkflowStep[]
  className?: string
  footerMessages?: WorkflowMessage[]
}

const TONE_CLASSES: Record<NonNullable<WorkflowMessage["tone"]>, string> = {
  info: "border-primary/40 text-primary",
  success: "border-success/50 text-success",
  warning: "border-amber-500/60 text-amber-500",
  error: "border-destructive/60 text-destructive",
}

export function WorkflowSidebar({ steps, className, footerMessages = [] }: WorkflowSidebarProps) {
  return (
    <Card className={cn("flex h-full flex-col border-line/60 bg-panel p-4", className)}>
      <CardHeader className="pb-4">
        <CardTitle className="text-base">Workflow</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-3 p-0">
        <ScrollArea className="h-full pr-2">
          <ol className="space-y-3 pb-4">
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
        {footerMessages.length ? (
          <div className="space-y-2 rounded-lg border border-line/50 bg-panel-2 px-3 py-2">
            <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Workflow messages</div>
            <ScrollArea className="max-h-32">
              <ul className="space-y-2 pr-2">
                {footerMessages.map((message) => (
                  <li
                    key={message.id}
                    className={cn(
                      "rounded-md border border-line/40 bg-panel px-3 py-2 text-xs text-foreground/90 shadow-sm",
                      message.tone ? TONE_CLASSES[message.tone] : ""
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span>{message.text}</span>
                      {message.timestamp ? (
                        <span className="ml-3 shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
                          {message.timestamp}
                        </span>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </ScrollArea>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}
