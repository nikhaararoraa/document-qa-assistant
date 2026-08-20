import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { createThread, listThreads, type ChatThread } from '@/lib/chat'
import { cn } from '@/lib/utils'
import { supabase } from '@/lib/supabase'

export function ThreadSidebar() {
  const navigate = useNavigate()
  const { session } = useAuth()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    let cancelled = false

    listThreads()
      .then((result) => {
        if (!cancelled) setThreads(result)
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : 'Failed to load threads')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [])

  async function handleNewChat() {
    setCreating(true)
    setError(null)
    try {
      const thread = await createThread()
      setThreads((current) => [thread, ...current])
      navigate(`/chat/${thread.id}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Failed to create thread')
    } finally {
      setCreating(false)
    }
  }

  return (
    <aside className="flex h-svh w-64 shrink-0 flex-col border-r">
      <div className="p-3">
        <Button onClick={handleNewChat} disabled={creating} className="w-full">
          {creating ? 'Creating…' : 'New chat'}
        </Button>
      </div>

      <ScrollArea className="min-h-0 flex-1">
        <nav className="flex flex-col gap-1 p-3 pt-0">
          {loading && <p className="px-2 text-sm text-muted-foreground">Loading…</p>}
          {error && <p className="px-2 text-sm text-destructive">{error}</p>}
          {!loading && !error && threads.length === 0 && (
            <p className="px-2 text-sm text-muted-foreground">No conversations yet.</p>
          )}
          {threads.map((thread) => (
            <NavLink
              key={thread.id}
              to={`/chat/${thread.id}`}
              className={({ isActive }) =>
                cn(
                  'truncate rounded-lg px-2.5 py-2 text-sm hover:bg-muted',
                  isActive && 'bg-muted font-medium',
                )
              }
            >
              {thread.title ?? 'Untitled conversation'}
            </NavLink>
          ))}
        </nav>
      </ScrollArea>

      <div className="flex items-center justify-between gap-2 border-t p-3">
        <span className="truncate text-sm text-muted-foreground">{session?.user.email}</span>
        <Button variant="outline" size="sm" onClick={() => supabase.auth.signOut()}>
          Sign out
        </Button>
      </div>
    </aside>
  )
}
