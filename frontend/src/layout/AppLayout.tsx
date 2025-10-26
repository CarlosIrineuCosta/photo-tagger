import { Outlet } from "react-router-dom"

import { StatusStrip, type StatusEntry } from "@/components/StatusStrip"
import { Topbar } from "@/components/Topbar"
import { Toaster } from "@/components/ui/toaster"
import { StatusLogProvider, useStatusLog } from "@/context/status-log"

type AppLayoutProps = {
  statusLog: StatusEntry[]
}

export function AppLayout({ statusLog }: AppLayoutProps) {
  return (
    <StatusLogProvider initialEntries={statusLog}>
      <AppLayoutShell />
    </StatusLogProvider>
  )
}

function AppLayoutShell() {
  const { entries } = useStatusLog()
  return (
    <div className="relative min-h-screen bg-background text-foreground">
      <Topbar />
      <div className="pb-16">
        <Outlet />
      </div>
      <StatusStrip items={entries} />
      <Toaster />
    </div>
  )
}
