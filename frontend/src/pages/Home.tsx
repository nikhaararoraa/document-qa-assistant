import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { supabase } from '@/lib/supabase'

type MeResponse = {
  id: string
  email: string
}

export function Home() {
  const { session } = useAuth()
  const [result, setResult] = useState<string | null>(null)
  const [checking, setChecking] = useState(false)

  async function checkBackend() {
    setChecking(true)
    setResult(null)
    try {
      const me = await api.get<MeResponse>('/auth/me')
      setResult(`Backend confirmed you as ${me.email} (id: ${me.id})`)
    } catch (error) {
      setResult(error instanceof ApiError ? `Error: ${error.message}` : 'Unknown error')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Signed in</CardTitle>
          <CardDescription>{session?.user.email}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button onClick={checkBackend} disabled={checking} className="w-full">
            {checking ? 'Checking…' : 'Test authenticated backend call'}
          </Button>
          {result && <p className="text-sm text-muted-foreground">{result}</p>}
          <Button variant="outline" onClick={() => supabase.auth.signOut()} className="w-full">
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}
