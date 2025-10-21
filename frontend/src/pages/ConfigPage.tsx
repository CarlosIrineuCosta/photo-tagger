import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { useStatusLog } from "@/context/status-log"
import { fetchConfig, updateConfig, type ApiConfig } from "@/lib/api"

type ConfigFormState = {
  root: string
  labels_file: string
  run_dir: string
  thumb_cache: string
  max_images: string
  topk: string
  model_name: string
}

const toFormState = (config: ApiConfig): ConfigFormState => ({
  root: config.root ?? "",
  labels_file: config.labels_file ?? "",
  run_dir: config.run_dir ?? "",
  thumb_cache: config.thumb_cache ?? "",
  max_images: String(config.max_images ?? ""),
  topk: String(config.topk ?? ""),
  model_name: config.model_name ?? "",
})

export function ConfigPage() {
  const { push: pushStatus } = useStatusLog()
  const [formState, setFormState] = useState<ConfigFormState | null>(null)
  const [initialConfig, setInitialConfig] = useState<ApiConfig | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadConfig = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchConfig()
      setInitialConfig(data)
      setFormState(toFormState(data))
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load configuration")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const isDirty = useMemo(() => {
    if (!formState || !initialConfig) {
      return false
    }
    const current = {
      root: formState.root.trim(),
      labels_file: formState.labels_file.trim(),
      run_dir: formState.run_dir.trim(),
      thumb_cache: formState.thumb_cache.trim(),
      max_images: Number(formState.max_images),
      topk: Number(formState.topk),
      model_name: formState.model_name.trim(),
    }
    return (
      current.root !== initialConfig.root ||
      current.labels_file !== initialConfig.labels_file ||
      current.run_dir !== initialConfig.run_dir ||
      current.thumb_cache !== initialConfig.thumb_cache ||
      current.max_images !== initialConfig.max_images ||
      current.topk !== initialConfig.topk ||
      current.model_name !== initialConfig.model_name
    )
  }, [formState, initialConfig])

  const handleChange = useCallback((field: keyof ConfigFormState) => {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value
      setFormState((prev) => (prev ? { ...prev, [field]: value } : prev))
    }
  }, [])

  const handleSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (!formState) {
        return
      }

      const trimmed = {
        root: formState.root.trim(),
        labels_file: formState.labels_file.trim(),
        run_dir: formState.run_dir.trim(),
        thumb_cache: formState.thumb_cache.trim(),
        model_name: formState.model_name.trim(),
      }
      const numericMaxImages = Number(formState.max_images)
      const numericTopk = Number(formState.topk)

      if (!trimmed.root || !trimmed.run_dir) {
        setError("Root and run directory are required.")
        return
      }
      if (!Number.isFinite(numericMaxImages) || numericMaxImages <= 0) {
        setError("Maximum images must be a positive number.")
        return
      }
      if (!Number.isFinite(numericTopk) || numericTopk <= 0) {
        setError("Top-K suggestions must be a positive number.")
        return
      }

      setSaving(true)
      try {
        const response = await updateConfig({
          ...trimmed,
          labels_file: trimmed.labels_file,
          thumb_cache: trimmed.thumb_cache,
          max_images: numericMaxImages,
          topk: numericTopk,
        })
        setInitialConfig(response.config)
        setFormState(toFormState(response.config))
        pushStatus({ message: "Configuration saved.", level: "success" })
        setError(null)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to update configuration"
        setError(message)
        pushStatus({ message, level: "error" })
      } finally {
        setSaving(false)
      }
    },
    [formState, pushStatus]
  )

  const handleReset = useCallback(() => {
    if (initialConfig) {
      setFormState(toFormState(initialConfig))
      setError(null)
    }
  }, [initialConfig])

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-10">
      <Card className="border-line/60 bg-panel">
        <CardHeader>
          <CardTitle className="text-xl">Configuration</CardTitle>
          <CardDescription>
            Manage the backend settings used by the CLI pipeline and FastAPI bridge. Updates persist to <code>config.yaml</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading && <p className="text-sm text-muted-foreground">Loading configuration…</p>}
          {!loading && formState && (
            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="root">Photo root</Label>
                  <Input
                    id="root"
                    value={formState.root}
                    onChange={handleChange("root")}
                    placeholder="/mnt/photos"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">Base directory scanned by the pipeline.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="labels_file">Labels source</Label>
                  <Input
                    id="labels_file"
                    value={formState.labels_file}
                    onChange={handleChange("labels_file")}
                    placeholder="labels"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">
                    Text file or directory (e.g. <code>labels</code>). When empty we fall back to a pack in <code>./labels</code>{" "}
                    or <code>root/labels.txt</code>.
                  </p>
                </div>
              </div>

              <div className="grid gap-5 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="run_dir">Output folder</Label>
                  <Input
                    id="run_dir"
                    value={formState.run_dir}
                    onChange={handleChange("run_dir")}
                    placeholder="runs"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">
                    Folder where the pipeline writes run artifacts (scores, exports, logs).
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="thumb_cache">Thumbnail cache</Label>
                  <Input
                    id="thumb_cache"
                    value={formState.thumb_cache}
                    onChange={handleChange("thumb_cache")}
                    placeholder="thumb_cache"
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">Folder used by <code>thumbs.py</code> to cache previews.</p>
                </div>
              </div>

              <div className="grid gap-5 md:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="max_images">Max images</Label>
                  <Input
                    id="max_images"
                    type="number"
                    min={1}
                    value={formState.max_images}
                    onChange={handleChange("max_images")}
                  />
                  <p className="text-xs text-muted-foreground">Limits how many items load into the gallery at once.</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="topk">Max labels</Label>
                  <Input id="topk" type="number" min={1} value={formState.topk} onChange={handleChange("topk")} />
                  <p className="text-xs text-muted-foreground">Maximum suggestions returned for each image.</p>
                </div>
                <div className="space-y-2 md:col-span-1 md:self-end">
                  <Label htmlFor="model_name">Model name</Label>
                  <Input
                    id="model_name"
                    value={formState.model_name}
                    placeholder="ViT-L-14"
                    readOnly
                    disabled
                    autoComplete="off"
                  />
                  <p className="text-xs text-muted-foreground">
                    Fixed for now. Model selection will become a dropdown in a future update.
                  </p>
                </div>
              </div>

              {error && <p className="text-sm text-destructive-foreground">{error}</p>}

              <Separator className="bg-line/60" />
              <div className="flex flex-wrap items-center gap-3">
                <Button type="submit" disabled={saving || !isDirty}>
                  {saving ? "Saving…" : "Save changes"}
                </Button>
                <Button type="button" variant="secondary" disabled={!isDirty || saving} onClick={handleReset}>
                  Reset
                </Button>
                <Button type="button" variant="ghost" onClick={() => void loadConfig()} disabled={loading || saving}>
                  Reload from disk
                </Button>
                {initialConfig && (
                  <span className="text-xs text-muted-foreground">
                    Config file: <code>config.yaml</code>
                  </span>
                )}
              </div>
            </form>
          )}
          {!loading && !formState && <p className="text-sm text-destructive-foreground">Configuration unavailable.</p>}
        </CardContent>
      </Card>
    </div>
  )
}
