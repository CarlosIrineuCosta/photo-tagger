import { cn } from "@/lib/utils"
import { X } from "lucide-react"
import { useEffect, useState } from "react"

export type ToastProps = {
  id: string
  title?: string
  description?: string
  variant?: "default" | "destructive" | "success"
  duration?: number
  onDismiss?: () => void
}

export function Toast({ title, description, variant = "default", duration = 5000, onDismiss }: ToastProps) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (duration > 0) {
      const timer = setTimeout(() => {
        setVisible(false)
        setTimeout(() => onDismiss?.(), 300) // Allow exit animation
      }, duration)
      return () => clearTimeout(timer)
    }
  }, [duration, onDismiss])

  const handleDismiss = () => {
    setVisible(false)
    setTimeout(() => onDismiss?.(), 300)
  }

  const variantClasses = {
    default: "border-border bg-background text-foreground",
    destructive: "border-destructive bg-destructive text-destructive-foreground",
    success: "border-green-200 bg-green-50 text-green-800",
  }

  return (
    <div
      className={cn(
        "relative flex w-full max-w-sm items-center justify-between space-x-4 overflow-hidden rounded-md border p-4 shadow-lg transition-all duration-300 ease-in-out",
        variantClasses[variant],
        visible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
      )}
    >
      <div className="grid gap-1">
        {title && <div className="text-sm font-semibold">{title}</div>}
        {description && <div className="text-sm opacity-90">{description}</div>}
      </div>
      <button
        onClick={handleDismiss}
        className="absolute right-2 top-2 rounded-md p-1 text-foreground/50 opacity-0 transition-opacity hover:text-foreground focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <X className="h-4 w-4" />
        <span className="sr-only">Close</span>
      </button>
    </div>
  )
}

export type ToastAction = {
  altText?: string
  onClick: () => void
  text: string
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
