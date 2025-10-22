type BlockingOverlayProps = {
  title: string
  message?: string
  tone?: "default" | "warning"
}

export function BlockingOverlay({ title, message, tone = "default" }: BlockingOverlayProps) {
  const toneClasses =
    tone === "warning"
      ? "border-destructive/80 bg-destructive/10 text-destructive"
      : "border-line/60 bg-panel text-foreground"
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm">
      <div
        className={[
          "rounded-xl px-7 py-5 shadow-2xl transition-all",
          "border-2",
          toneClasses,
        ].join(" ")}
      >
        <p className="text-base font-semibold">{title}</p>
        {message ? <p className="mt-1 text-sm text-muted-foreground">{message}</p> : null}
      </div>
    </div>
  )
}
