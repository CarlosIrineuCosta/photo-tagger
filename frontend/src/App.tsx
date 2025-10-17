import { Navigate, RouterProvider, createBrowserRouter } from "react-router-dom"

import { AppLayout } from "@/layout/AppLayout"
import { ConfigPage } from "@/pages/ConfigPage"
import { GalleryPage } from "@/pages/GalleryPage"
import { HelpPage } from "@/pages/HelpPage"
import { LoginPage } from "@/pages/LoginPage"
import type { StatusEntry } from "@/components/StatusStrip"

const STATUS_LOG: StatusEntry[] = [
  { id: "1", message: "Exported 24 items to runs/2025-10-17-001", level: "success" },
  { id: "2", message: "Queued 120 new thumbnails", level: "info" },
  { id: "3", message: "Sidecars synced to ./runs/latest/sidecars", level: "success" },
  { id: "4", message: "Medoid computation finished for /portraits", level: "info" },
]

const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout statusLog={STATUS_LOG} />,
    children: [
      { index: true, element: <GalleryPage /> },
      { path: "config", element: <ConfigPage /> },
      { path: "help", element: <HelpPage /> },
      { path: "login", element: <LoginPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
])

function App() {
  return <RouterProvider router={router} />
}

export default App
