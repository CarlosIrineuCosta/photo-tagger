import * as React from "react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface SegmentedControlProps {
  value: string
  onValueChange: (value: string) => void
  options: Array<{
    value: string
    label: string
    disabled?: boolean
  }>
  className?: string
}

export function SegmentedControl({ value, onValueChange, options, className }: SegmentedControlProps) {
  return (
    <div className={cn("inline-flex h-9 items-center rounded-lg bg-muted p-1 text-muted-foreground", className)}>
      {options.map((option) => (
        <Button
          key={option.value}
          variant="ghost"
          size="sm"
          className={cn(
            "h-7 rounded-md px-3 text-sm font-medium transition-all",
            value === option.value
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
          onClick={() => onValueChange(option.value)}
          disabled={option.disabled}
        >
          {option.label}
        </Button>
      ))}
    </div>
  )
}
