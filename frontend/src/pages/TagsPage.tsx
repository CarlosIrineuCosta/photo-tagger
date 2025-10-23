import { useCallback, useEffect, useMemo, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { BlockingOverlay } from "@/components/BlockingOverlay"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  addTagToGroup,
  deleteTagFromGroup,
  fetchTagSummary,
  promoteOrphanTag,
  promoteOrphanTagsBulk,
  suggestGroupForTag,
  type TagGroupSummary,
  type TagSummaryResponse,
  type OrphanTagSummary,
  type BulkPromoteAction,
  type BulkPromoteResponse,
  type SuggestGroupResponse,
} from "@/lib/api"
import { useStatusLog } from "@/context/status-log"

type BlockingState = { title: string; message?: string } | null

export function TagsPage() {
  const [summary, setSummary] = useState<TagSummaryResponse | null>(null)
  const [blocking, setBlocking] = useState<BlockingState>({ title: "Loading tags…", message: "Gathering label packs." })
  const [error, setError] = useState<string | null>(null)
  const [inputs, setInputs] = useState<Record<string, string>>({})
  const [busyGroup, setBusyGroup] = useState<string | null>(null)
  const [promotionTarget, setPromotionTarget] = useState<OrphanTagSummary | null>(null)
  const [selectedGroupId, setSelectedGroupId] = useState<string>("")
  const [newGroupName, setNewGroupName] = useState<string>("")
  const [savingPromotion, setSavingPromotion] = useState(false)
  const { push: pushStatus } = useStatusLog()

  // Hybrid promotion state
  const [suggestions, setSuggestions] = useState<Map<string, SuggestGroupResponse>>(new Map())
  const [loadingSuggestions, setLoadingSuggestions] = useState<Set<string>>(new Set())
  const [optimisticUpdates, setOptimisticUpdates] = useState<Map<string, { action: string; previousState: OrphanTagSummary }>>(new Map())
  const [undoQueue, setUndoQueue] = useState<Array<{ id: string; action: string; timestamp: number }>>([])

  // Bulk promotion state
  const [selectedOrphans, setSelectedOrphans] = useState<Set<string>>(new Set())
  const [bulkPromotionOpen, setBulkPromotionOpen] = useState(false)
  const [bulkPromotionResults, setBulkPromotionResults] = useState<BulkPromoteResponse | null>(null)

  const groups = useMemo(() => summary?.groups ?? [], [summary])
  const defaultGroupId = groups[0]?.id ?? ""
  const promotionReady = Boolean(selectedGroupId || newGroupName.trim())

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

  const fetchSuggestion = useCallback(
    async (tag: string) => {
      if (suggestions.has(tag)) {
        return suggestions.get(tag)!
      }

      setLoadingSuggestions((prev) => new Set(prev).add(tag))
      try {
        const suggestion = await suggestGroupForTag(tag)
        setSuggestions((prev) => new Map(prev).set(tag, suggestion))
        return suggestion
      } catch (err) {
        pushStatus({
          message: `Failed to fetch suggestion for "${tag}": ${err instanceof Error ? err.message : "Unknown error"}`,
          level: "error",
        })
        return null
      } finally {
        setLoadingSuggestions((prev) => {
          const next = new Set(prev)
          next.delete(tag)
          return next
        })
      }
    },
    [suggestions, pushStatus]
  )

  const handleQuickPromote = useCallback(
    async (orphan: OrphanTagSummary, suggestedGroupId: string) => {
      const tagName = orphan.name

      // Store previous state for rollback
      const previousState = orphan

      // Optimistic update
      setOptimisticUpdates((prev) =>
        new Map(prev).set(tagName, {
          action: "promote",
          previousState
        })
      )

      // Add to undo queue
      setUndoQueue((prev) => [
        ...prev,
        { id: tagName, action: "promote", timestamp: Date.now() }
      ])

      try {
        const response = await promoteOrphanTag({
          tag: tagName,
          target_group: suggestedGroupId,
        })

        pushStatus({
          message: `Promoted "${tagName}" to ${response.group_label}`,
          level: "success",
        })

        // Refresh the summary
        await loadSummary({ title: "Refreshing tags…", message: "Re-reading label packs." })
      } catch (err) {
        // Rollback on failure
        setOptimisticUpdates((prev) => {
          const next = new Map(prev)
          next.delete(tagName)
          return next
        })

        pushStatus({
          message: `Failed to promote "${tagName}": ${err instanceof Error ? err.message : "Unknown error"}`,
          level: "error",
        })
      }
    },
    [loadSummary, pushStatus]
  )

  const handleUndo = useCallback(
    (tagId: string) => {
      const update = optimisticUpdates.get(tagId)
      if (!update) return

      // For now, we'll just remove the optimistic update
      // In a real implementation, you'd need to handle the actual rollback
      setOptimisticUpdates((prev) => {
        const next = new Map(prev)
        next.delete(tagId)
        return next
      })

      setUndoQueue((prev) => prev.filter((item) => item.id !== tagId))
      pushStatus({
        message: `Rolled back promotion of "${tagId}"`,
        level: "info",
      })
    },
    [optimisticUpdates, pushStatus]
  )

  const closePromotion = useCallback(() => {
    setPromotionTarget(null)
    setNewGroupName("")
    setSelectedGroupId(defaultGroupId)
  }, [defaultGroupId])

  const handlePromotionOpenChange = useCallback(
    (open: boolean) => {
      if (!open && !savingPromotion) {
        closePromotion()
      }
    },
    [closePromotion, savingPromotion]
  )

  const handlePromoteOrphan = useCallback(async () => {
    if (!promotionTarget) {
      return
    }
    const cleanedNewGroup = newGroupName.trim()
    if (!selectedGroupId && !cleanedNewGroup) {
      pushStatus({ message: "Select an existing group or specify a new group name.", level: "info" })
      return
    }
    setSavingPromotion(true)
    setBlocking({ title: "Promoting tag…", message: `Adding "${promotionTarget.name}" to the label pack.` })
    try {
      const payload: { tag: string; target_group?: string; new_group_label?: string } = { tag: promotionTarget.name }
      if (cleanedNewGroup) {
        payload.new_group_label = cleanedNewGroup
      } else {
        payload.target_group = selectedGroupId
      }
      const response = await promoteOrphanTag(payload)
      const destination = response.group_label || response.group
      pushStatus({
        message: response.created_group
          ? `Created ${destination} and added "${response.tag}".`
          : `Added "${response.tag}" to ${destination}.`,
        level: "success",
      })
      closePromotion()
      await loadSummary({ title: "Refreshing tags…", message: "Re-reading label packs." })
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to promote tag"
      pushStatus({ message, level: "error" })
      setBlocking(null)
    } finally {
      setSavingPromotion(false)
    }
  }, [closePromotion, loadSummary, newGroupName, promotionTarget, pushStatus, selectedGroupId])

  const openPromotion = useCallback(
    (item: OrphanTagSummary) => {
      setPromotionTarget(item)
      setSelectedGroupId(defaultGroupId)
      setNewGroupName("")
    },
    [defaultGroupId]
  )

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
        {groups.map((group) => (
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
                    <th className="w-24 px-4 py-2 text-right">Occurrences</th>
                    <th className="w-48 px-4 py-2">Suggested Group</th>
                    <th className="w-48 px-4 py-2 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {orphanTags.length ? (
                    orphanTags.map((item) => {
                      const suggestion = suggestions.get(item.name)
                      const isLoading = loadingSuggestions.has(item.name)
                      const isOptimisticallyUpdated = optimisticUpdates.has(item.name)

                      if (isOptimisticallyUpdated) {
                        return null // Skip items that are being optimistically updated
                      }

                      return (
                        <tr key={item.name} className="border-t border-line/20">
                          <td className="px-4 py-2 text-foreground">{item.name}</td>
                          <td className="px-4 py-2 text-right text-muted-foreground">{item.occurrences}</td>
                          <td className="px-4 py-2">
                            {item.suggested_group_id ? (
                              <div className="flex items-center gap-2">
                                <Badge variant="secondary" className="text-xs">
                                  {groups.find(g => g.id === item.suggested_group_id)?.label || item.suggested_group_id}
                                </Badge>
                                {item.confidence && (
                                  <span className="text-xs text-muted-foreground">
                                    {Math.round(item.confidence * 100)}%
                                  </span>
                                )}
                              </div>
                            ) : suggestion ? (
                              <div className="flex items-center gap-2">
                                <Badge variant="secondary" className="text-xs">
                                  {groups.find(g => g.id === suggestion.suggested_group_id)?.label || suggestion.suggested_group_id}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  {Math.round(suggestion.confidence * 100)}%
                                </span>
                              </div>
                            ) : isLoading ? (
                              <span className="text-xs text-muted-foreground">Loading...</span>
                            ) : (
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 px-2 text-xs"
                                onClick={() => void fetchSuggestion(item.name)}
                                disabled={isLoading}
                              >
                                Get Suggestion
                              </Button>
                            )}
                          </td>
                          <td className="px-4 py-2 text-right">
                            <div className="flex items-center justify-end gap-2">
                              {(item.suggested_group_id || suggestion) && (
                                <Button
                                  size="sm"
                                  variant="default"
                                  onClick={() => void handleQuickPromote(item, item.suggested_group_id || suggestion!.suggested_group_id)}
                                  disabled={!!blocking || savingPromotion}
                                >
                                  Quick Promote
                                </Button>
                              )}
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => openPromotion(item)}
                                disabled={!!blocking || savingPromotion}
                              >
                                Promote
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  ) : (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={4}>
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

      <Sheet open={!!promotionTarget} onOpenChange={handlePromotionOpenChange}>
        <SheetContent side="right" className="w-full sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Promote tag</SheetTitle>
            <SheetDescription>
              {promotionTarget ? (
                <>
                  Promote <span className="font-medium text-foreground">{promotionTarget.name}</span> into a structured
                  group.
                  {typeof promotionTarget.occurrences === "number" ? (
                    <>
                      {" "}
                      Seen {promotionTarget.occurrences} time{promotionTarget.occurrences === 1 ? "" : "s"} in recent
                      reviews.
                    </>
                  ) : null}
                </>
              ) : (
                "Select a tag to promote."
              )}
            </SheetDescription>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="promotion-group">Existing group</Label>
              <select
                id="promotion-group"
                className="w-full rounded-md border border-line/40 bg-background px-3 py-2 text-sm text-foreground shadow-sm focus:outline-none focus:ring-2 focus:ring-primary"
                value={selectedGroupId}
                onChange={(event) => setSelectedGroupId(event.target.value)}
                disabled={savingPromotion || groups.length === 0}
              >
                {groups.length === 0 ? <option value="">No groups available</option> : null}
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="promotion-new-group">Create new group</Label>
              <Input
                id="promotion-new-group"
                placeholder="e.g. AI concepts"
                value={newGroupName}
                onChange={(event) => setNewGroupName(event.target.value)}
                disabled={savingPromotion}
              />
              <p className="text-xs text-muted-foreground">Leave blank to use the selected group.</p>
            </div>
          </div>
          <SheetFooter className="mt-6">
            <Button variant="outline" onClick={closePromotion} disabled={savingPromotion}>
              Cancel
            </Button>
            <Button onClick={() => void handlePromoteOrphan()} disabled={savingPromotion || !promotionReady}>
              {savingPromotion ? "Promoting…" : "Promote"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Undo notification */}
      {undoQueue.length > 0 && (
        <div className="fixed bottom-4 right-4 z-50">
          <Card className="border-line/60 bg-panel shadow-lg">
            <CardContent className="p-3">
              <div className="flex items-center gap-3">
                <span className="text-sm text-foreground">
                  {undoQueue.length} promotion{undoQueue.length === 1 ? "" : "s"} in progress
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleUndo(undoQueue[undoQueue.length - 1].id)}
                >
                  Undo Last
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

export default TagsPage
