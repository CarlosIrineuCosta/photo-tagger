import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

const helpSections = [
  {
    title: "Workflow basics",
    body:
      "Scan, generate thumbnails, embed with CLIP, score against labels, then approve and export. Each stage maps to a CLI command documented in README.md.",
  },
  {
    title: "Keyboard shortcuts",
    body:
      "Shortcuts will be added once we finalize component focus states. Planned bindings: numeric keys to toggle labels, J/K for navigation, and S to save approved tags.",
  },
  {
    title: "Troubleshooting",
    body:
      "If thumbnails look outdated, clear thumb_cache/. For stale scores, rerun the embedding + scoring CLI steps before exporting. CLIP model issues appear in logs/ directory.",
  },
]

export function HelpPage() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-10">
      <Card className="border-line/60 bg-panel">
        <CardHeader>
          <CardTitle>Help &amp; Reference</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="max-h-[60vh] px-6 pb-6">
            <div className="space-y-6 text-sm text-muted-foreground">
              {helpSections.map((section) => (
                <section key={section.title}>
                  <h2 className="text-base font-medium text-foreground">{section.title}</h2>
                  <p className="mt-2 leading-relaxed">{section.body}</p>
                </section>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
