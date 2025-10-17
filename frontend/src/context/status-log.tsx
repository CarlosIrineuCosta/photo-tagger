import { createContext, useCallback, useContext, useMemo, useState } from "react"
import type { ReactNode } from "react"

import type { StatusEntry } from "@/components/StatusStrip"

type StatusLogContextValue = {
  entries: StatusEntry[]
  push: (entry: Omit<StatusEntry, "id" | "timestamp"> & Partial<Pick<StatusEntry, "id" | "timestamp">>) => void
  clear: () => void
}

const StatusLogContext = createContext<StatusLogContextValue | null>(null)

type StatusLogProviderProps = {
  initialEntries: StatusEntry[]
  children: ReactNode
}

export function StatusLogProvider({ initialEntries, children }: StatusLogProviderProps) {
  const [entries, setEntries] = useState<StatusEntry[]>(initialEntries)

  const push = useCallback<StatusLogContextValue["push"]>((entry) => {
    const id = entry.id ?? crypto.randomUUID()
    const timestamp = entry.timestamp ?? new Date().toLocaleTimeString()
    setEntries((prev) => {
      const next = [...prev, { ...entry, id, timestamp }]
      if (next.length > 20) {
        return next.slice(next.length - 20)
      }
      return next
    })
  }, [])

  const clear = useCallback(() => setEntries([]), [])

  const value = useMemo(() => ({ entries, push, clear }), [entries, push, clear])

  return <StatusLogContext.Provider value={value}>{children}</StatusLogContext.Provider>
}

export function useStatusLog() {
  const context = useContext(StatusLogContext)
  if (!context) {
    throw new Error("useStatusLog must be used within a StatusLogProvider")
  }
  return context
}
