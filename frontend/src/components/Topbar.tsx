import { NavigationMenu, NavigationMenuItem, NavigationMenuLink, NavigationMenuList } from "@/components/ui/navigation-menu"
import { cn } from "@/lib/utils"
import { NavLink } from "react-router-dom"

type TopbarProps = {
  routes?: Array<{ label: string; href: string }>
}

const DEFAULT_ROUTES = [
  { label: "Gallery", href: "/" },
  { label: "Config", href: "/config" },
  { label: "Tags", href: "/tags" },
  { label: "Help", href: "/help" },
  { label: "Login", href: "/login" },
]

export function Topbar({ routes = DEFAULT_ROUTES }: TopbarProps) {
  return (
    <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-line/60 bg-panel/90 px-5 backdrop-blur-md">
      <div className="font-semibold tracking-wide">Lumen</div>
      <NavigationMenu>
        <NavigationMenuList className="gap-2">
          {routes.map((route) => (
            <NavigationMenuItem key={route.label}>
              <NavigationMenuLink asChild>
                <NavLink
                  to={route.href}
                  end={route.href === "/"}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground",
                      isActive && "bg-panel-2 text-foreground"
                    )
                  }
                >
                  {route.label}
                </NavLink>
              </NavigationMenuLink>
            </NavigationMenuItem>
          ))}
        </NavigationMenuList>
      </NavigationMenu>
    </header>
  )
}
