import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

type HelpItem =
  | { kind: "text"; text: string }
  | { kind: "command"; command: string; detail?: string }

type HelpSection = {
  title: string
  description?: string
  items?: HelpItem[]
}

const helpSections: HelpSection[] = [
  {
    title: "Quick start",
    description:
      "Bring the stack online with the helper script, then open the gallery in your browser. These commands assume you are in the repository root.",
    items: [
      { kind: "command", command: "./start-tagger.sh", detail: "Boots FastAPI + Vite, creating .venv/ if needed." },
      { kind: "command", command: "python scripts/smoke_test.py --wipe", detail: "Refreshes fixtures for UI testing." },
      { kind: "command", command: "http://127.0.0.1:5173", detail: "Open the React interface once the dev server reports ready." },
    ],
  },
  {
    title: "Review flow",
    description:
      "The gallery grid mirrors `mock_v2.html`: toggle CLIP suggestions to approve labels and move through the workflow.",
    items: [
      { kind: "text", text: "Letterbox toggle switches between fit and center crop modes." },
      { kind: "text", text: "Workflow sidebar tracks pipeline stages; open it on large batches to confirm scoring status." },
      { kind: "text", text: "Status strip records the last 20 operations (saves, exports, process launches)." },
    ],
  },
  {
    title: "Configuration tips",
    description:
      "Use the Config page to edit `config.yaml`. Changes persist immediately on save and reset the API caches.",
    items: [
      { kind: "text", text: "Root path must be a readable photo directory." },
      { kind: "text", text: "Leave labels_file blank to fall back to <root>/labels.txt." },
      { kind: "text", text: "max_images controls initial gallery load; keep it modest for laptops." },
    ],
  },
  {
    title: "CLI reference",
    description: "Match UI actions with their CLI counterparts when you need to run stages manually.",
    items: [
      { kind: "command", command: "python -m app.cli.tagger scan --root <path>" },
      { kind: "command", command: "python -m app.cli.tagger thumbs --root <path>" },
      { kind: "command", command: "python -m app.cli.tagger score --root <path>" },
      { kind: "command", command: "python -m app.cli.tagger export --root <path> --mode csv" },
    ],
  },
  {
    title: "Troubleshooting",
    description: "Common fixes while the refactor settles.",
    items: [
      {
        kind: "command",
        command: "npm config set audit false && npm install --no-progress",
        detail: "Run inside frontend/ if npm stalls on audit.",
      },
      { kind: "text", text: "For missing thumbnails, delete thumb_cache/ and rerun the thumbnail stage." },
      {
        kind: "text",
        text: "Torch stack must stay pinned to torch==2.2.2 and torchvision==0.17.2 to avoid long resolver loops.",
      },
    ],
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
                <section key={section.title} className="space-y-2">
                  <h2 className="text-base font-medium text-foreground">{section.title}</h2>
                  {section.description && <p className="leading-relaxed">{section.description}</p>}
                  {section.items && section.items.length > 0 && (
                    <ul className="list-disc space-y-1 pl-5">
                      {section.items.map((item, index) => {
                        if (item.kind === "text") {
                          return <li key={`${item.text}-${index}`}>{item.text}</li>
                        }
                        return (
                          <li key={`${item.command}-${index}`} className="space-y-1">
                            <code className="rounded bg-panel-2 px-1 py-0.5 font-mono text-xs text-foreground/90">
                              {item.command}
                            </code>
                            {item.detail && <div className="text-xs text-muted-foreground">{item.detail}</div>}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </section>
              ))}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}
