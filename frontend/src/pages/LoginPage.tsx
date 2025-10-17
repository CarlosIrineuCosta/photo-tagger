import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export function LoginPage() {
  return (
    <div className="flex min-h-[calc(100vh-120px)] items-center justify-center px-6 py-10">
      <Card className="w-full max-w-md border-line/60 bg-panel">
        <CardHeader>
          <CardTitle>Operator Login</CardTitle>
          <CardDescription>Placeholder form — hook into FastAPI session endpoints in Phase 2.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" placeholder="operator@photo-tagger.local" disabled />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" placeholder="••••••••" disabled />
          </div>
          <Button className="w-full" disabled>
            Sign in
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
