import { useCallback, useEffect, useMemo, useState } from "react"

import { BlockingOverlay } from "@/components/BlockingOverlay"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  addTagToGroup,
  deleteTagFromGroup,
  fetchTagSummary,
  type TagGroupSummary,
  type TagSummaryResponse,
} from "@/lib/api"
import { useStatusLog } from "@/context/status-log"

type BlockingState = { title: string; message?: string } | null

export function TagsPage() {
  const [summary, setSummary] = useState<TagSummaryResponse | null>(null)
  const [blocking, setBlocking] = useState<BlockingState>({ title: "Loading tags…", message: "Gathering label packs." })
  const [error, setError] = useState<string | null>(null)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [busyGroup, setBusyGroup] = useState<string | null>(null)
  const { push: pushStatus } = useStatusLog()

  const loadSummary = useCallback(
    async (overlay?: BlockingState) => {
      if (overlay) {
        setBlocking(overlay)
      } else if (!summary) {
        setBlocking({ title: "Loading tags…", message: "Gathering label packs." })
      }
      try {
        const data = await fetchTagSummary()
        setSummary(data)
        setError(null)
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unable to load tag summary"
        setError(message)
        pushStatus({ message, level: "error" })
      } finally {
        setBlocking(null)
      }
    },
    [pushStatus, summary]
  )

  useEffect(() => {
    void loadSummary()
  }, [loadSummary])

  const handleInputChange = useCallback((groupId: string, value: string) => {
    setInputs((prev) => ({ ...prev, [groupId]: value }))
  }, [])

  const handleAddTag = useCallback(
    async (group: TagGroupSummary) => {
      const value = (inputs[group.id] ?? "").trim()
      if (!value) {
        pushStatus({ message: "Enter a tag before adding.", level: "info" })
        return
      }
      setBusyGroup(group.id)
      setBlocking({ title: "Adding tag…", message: `Updating ${group.label.toLowerCase()} labels.` })
      try {
        await addTagToGroup({ group: group.id, tag: value })
        pushStatus({ message: `Added "${value}" to ${group.label}.`, level: "success" })
        setInputs((prev) => ({ ...prev, [group.id]: "" }))
        await loadSummary()
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to add tag"
        pushStatus({ message, level: "error" })
        setBlocking(null)
      } finally {
        setBusyGroup(null)
      }
    },
    [inputs, loadSummary, pushStatus]
  )

  const handleDeleteTag = useCallback(
    async (group: TagGroupSummary, tag: string) => {
      setBusyGroup(group.id)
      setBlocking({ title: "Removing tag…", message: `Editing ${group.label.toLowerCase()} labels.` })
      try {
        await deleteTagFromGroup({ group: group.id, tag })
        pushStatus({ message: `Removed "${tag}" from ${group.label}.`, level: "success" })
        await loadSummary()
      } catch (err) {
        const message = err instanceof Error ? err.message : "Failed to remove tag"
        pushStatus({ message, level: "error" })
        setBlocking(null)
      } finally {
        setBusyGroup(null)
      }
    },
    [loadSummary, pushStatus]
  )

  const orphanTags = useMemo(() => summary?.orphan_tags ?? [], [summary])
  const stats = summary?.stats ?? {}

  return (
    <div className="mx-auto w-full max-w-[1920px] px-4 py-6 lg:px-6">
      {blocking ? <BlockingOverlay title={blocking.title} message={blocking.message} tone="warning" /> : null}
      <div className="flex flex-col gap-3 pb-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Tag Library</h1>
          <p className="text-sm text-muted-foreground">
            Review structured label packs, capture new tags from recent reviews, and keep the vocabulary aligned.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
          <span>
            Groups: <strong>{stats.groups ?? 0}</strong>
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>
            Total labels: <strong>{stats.total_labels ?? 0}</strong>
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>
            Orphan labels: <strong>{stats.orphan_labels ?? 0}</strong>
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>
            Tags observed: <strong>{stats.samples_indexed ?? 0}</strong>
          </span>
          <Button
            size="sm"
            variant="outline"
            className="ml-auto"
            onClick={() => loadSummary({ title: "Refreshing tags…", message: "Re-reading label packs." })}
            disabled={!!blocking}
          >
            Refresh
          </Button>
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {summary?.groups.map((group) => (
          <Card key={group.id} className="border-line/60 bg-panel">
            <CardHeader>
              <CardTitle className="text-lg font-semibold text-foreground">{group.label}</CardTitle>
              <p className="text-xs text-muted-foreground">{group.tags.length} labels · {group.path}</p>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder={`Add ${group.label.toLowerCase()} tag`}
                  value={inputs[group.id] ?? ""}
                  onChange={(event) => handleInputChange(group.id, event.target.value)}
                  disabled={!!blocking || busyGroup === group.id}
                />
                <Button
                  onClick={() => void handleAddTag(group)}
                  disabled={!!blocking || busyGroup === group.id}
                >
                  Add
                </Button>
              </div>
              <ScrollArea className="h-64 rounded-md border border-line/40">
                <ul className="divide-y divide-line/30 text-sm">
                  {group.tags.map((tag) => (
                    <li key={tag} className="flex items-center justify-between px-3 py-2">
                      <span className="truncate text-foreground">{tag}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => void handleDeleteTag(group, tag)}
                        disabled={!!blocking || busyGroup === group.id}
                      >
                        Remove
                      </Button>
                    </li>
                  ))}
                  {group.tags.length === 0 ? (
                    <li className="px-3 py-2 text-muted-foreground">No tags yet.</li>
                  ) : null}
                </ul>
              </ScrollArea>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-6 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-foreground">Orphan Tags</h2>
          <p className="text-xs text-muted-foreground">
            Tags seen in recent reviews but not yet part of the structured pack.
          </p>
        </div>
        <Card className="border-line/60 bg-panel">
          <CardContent className="p-0">
            <ScrollArea className="h-60">
              <table className="w-full table-fixed border-collapse text-left text-sm">
                <thead className="sticky top-0 bg-panel-2">
                  <tr className="border-b border-line/40 text-muted-foreground">
                    <th className="px-4 py-2">Tag</th>
                    <th className="w-28 px-4 py-2 text-right">Occurrences</th>
                  </tr>
                </thead>
                <tbody>
                  {orphanTags.length ? (
                    orphanTags.map((item) => (
                      <tr key={item.name} className="border-t border-line/20">
                        <td className="px-4 py-2 text-foreground">{item.name}</td>
                        <td className="px-4 py-2 text-right text-muted-foreground">{item.occurrences}</td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={2}>
                        No orphan tags detected in the latest run.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default TagsPage
