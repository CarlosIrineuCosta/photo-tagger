import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Textarea } from "@/components/ui/textarea"
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
import { useStatusLog } from "@/context/status-log"

interface LLMEnhancerPanelProps {
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  imageId: string
  currentTags: string[]
  onTagsUpdate: (tags: string[]) => void
}

interface EnhancementRequest {
  context: string
  customPrompt?: string
  enhanceExisting: boolean
  maxSuggestions: number
}

interface EnhancedTag {
  tag: string
  confidence: number
  reasoning: string
  category: string
}

export function LLMEnhancerPanel({
  isOpen,
  onOpenChange,
  imageId,
  currentTags,
  onTagsUpdate
}: LLMEnhancerPanelProps) {
  const [isProcessing, setIsProcessing] = useState(false)
  const [enhancedTags, setEnhancedTags] = useState<EnhancedTag[]>([])
  const [selectedEnhancedTags, setSelectedEnhancedTags] = useState<Set<string>>(new Set())
  const [request, setRequest] = useState<EnhancementRequest>({
    context: "",
    customPrompt: "",
    enhanceExisting: true,
    maxSuggestions: 10
  })
  const { push: pushStatus } = useStatusLog()

  const handleEnhance = useCallback(async () => {
    setIsProcessing(true)
    try {
      // Call the LLM enhancer API (stub for now)
      const response = await fetch('/api/enhanced/llm-enhance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          image_id: imageId,
          current_tags: currentTags,
          ...request
        })
      })

      if (!response.ok) {
        throw new Error('Failed to enhance tags')
      }

      const data = await response.json()
      setEnhancedTags(data.suggestions || [])

      pushStatus({
        message: `Generated ${data.suggestions?.length || 0} enhanced tag suggestions`,
        level: "success"
      })
    } catch (error) {
      pushStatus({
        message: `LLM enhancement failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
        level: "error"
      })

      // Mock response for development
      const mockSuggestions: EnhancedTag[] = [
        { tag: "portrait", confidence: 0.92, reasoning: "Subject appears to be a person with clear facial features", category: "composition" },
        { tag: "natural_light", confidence: 0.87, reasoning: "Soft lighting suggests natural illumination", category: "lighting" },
        { tag: "outdoor", confidence: 0.79, reasoning: "Background elements indicate outdoor setting", category: "location" },
        { tag: "candid", confidence: 0.75, reasoning: "Subject appears unaware of camera", category: "style" },
        { tag: "warm_tones", confidence: 0.68, reasoning: "Color palette dominated by warm hues", category: "color" }
      ]
      setEnhancedTags(mockSuggestions)
    } finally {
      setIsProcessing(false)
    }
  }, [imageId, currentTags, request, pushStatus])

  const handleApplyEnhancements = useCallback(() => {
    const newTags = Array.from(selectedEnhancedTags)
    const combinedTags = [...new Set([...currentTags, ...newTags])]
    onTagsUpdate(combinedTags)

    pushStatus({
      message: `Applied ${newTags.length} enhanced tags`,
      level: "success"
    })

    onOpenChange(false)
  }, [selectedEnhancedTags, currentTags, onTagsUpdate, onOpenChange, pushStatus])

  const handleTagToggle = useCallback((tag: string) => {
    setSelectedEnhancedTags(prev => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }, [])

  const handleClose = useCallback(() => {
    if (!isProcessing) {
      onOpenChange(false)
      // Reset state when closing
      setEnhancedTags([])
      setSelectedEnhancedTags(new Set())
    }
  }, [isProcessing, onOpenChange])

  useEffect(() => {
    if (isOpen) {
      // Auto-generate context from current tags
      setRequest(prev => ({
        ...prev,
        context: `Current tags: ${currentTags.join(', ')}`
      }))
    }
  }, [isOpen, currentTags])

  return (
    <Sheet open={isOpen} onOpenChange={handleClose}>
      <SheetContent side="right" className="w-full sm:max-w-2xl">
        <SheetHeader>
          <SheetTitle>LLM Tag Enhancer</SheetTitle>
          <SheetDescription>
            Use AI to generate contextual tag suggestions based on the image content and existing tags.
          </SheetDescription>
        </SheetHeader>

        <div className="mt-6 space-y-6">
          {/* Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Enhancement Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="context">Context</Label>
                <Textarea
                  id="context"
                  placeholder="Describe the context or subject matter..."
                  value={request.context}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRequest(prev => ({ ...prev, context: e.target.value }))}
                  rows={3}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="custom-prompt">Custom Prompt (Optional)</Label>
                <Textarea
                  id="custom-prompt"
                  placeholder="Custom instructions for tag generation..."
                  value={request.customPrompt}
                  onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRequest(prev => ({ ...prev, customPrompt: e.target.value }))}
                  rows={2}
                />
              </div>

              <div className="flex items-center gap-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    id="enhance-existing"
                    checked={request.enhanceExisting}
                    onChange={(e) => setRequest(prev => ({ ...prev, enhanceExisting: e.target.checked }))}
                  />
                  <Label htmlFor="enhance-existing">Enhance existing tags</Label>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="max-suggestions">Max Suggestions</Label>
                  <Input
                    id="max-suggestions"
                    type="number"
                    min="1"
                    max="20"
                    value={request.maxSuggestions}
                    onChange={(e) => setRequest(prev => ({ ...prev, maxSuggestions: parseInt(e.target.value) || 10 }))}
                    className="w-20"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action Button */}
          <div className="flex justify-center">
            <Button
              onClick={handleEnhance}
              disabled={isProcessing || !request.context.trim()}
              className="w-full max-w-xs"
            >
              {isProcessing ? "Generating Suggestions..." : "Generate Enhanced Tags"}
            </Button>
          </div>

          {/* Results */}
          {enhancedTags.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Enhanced Tag Suggestions</CardTitle>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{enhancedTags.length} suggestions</span>
                  <Separator orientation="vertical" className="h-4" />
                  <span>{selectedEnhancedTags.size} selected</span>
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Tag</TableHead>
                      <TableHead>Confidence</TableHead>
                      <TableHead>Category</TableHead>
                      <TableHead>Reasoning</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {enhancedTags.map((tag) => (
                      <TableRow
                        key={tag.tag}
                        className={selectedEnhancedTags.has(tag.tag) ? "bg-primary/5" : ""}
                      >
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <input
                              type="checkbox"
                              checked={selectedEnhancedTags.has(tag.tag)}
                              onChange={() => handleTagToggle(tag.tag)}
                            />
                            <span className="font-medium">{tag.tag}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={tag.confidence > 0.8 ? "default" : tag.confidence > 0.6 ? "secondary" : "outline"}>
                            {Math.round(tag.confidence * 100)}%
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs">
                            {tag.category}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {tag.reasoning}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </div>

        <SheetFooter className="mt-6">
          <Button variant="outline" onClick={handleClose} disabled={isProcessing}>
            Cancel
          </Button>
          <Button
            onClick={handleApplyEnhancements}
            disabled={selectedEnhancedTags.size === 0 || isProcessing}
          >
            Apply {selectedEnhancedTags.size} Enhanced Tag{selectedEnhancedTags.size === 1 ? "" : "s"}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}
