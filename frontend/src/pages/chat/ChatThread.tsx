import { useChat } from '@ai-sdk/react'
import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ChatInput } from '@/components/chat/ChatInput'
import { MessageList } from '@/components/chat/MessageList'
import { ApiError } from '@/lib/api'
import { getThreadMessages } from '@/lib/chat'
import { createChatTransport } from '@/lib/chatTransport'

export function ChatThread() {
  const { threadId } = useParams<{ threadId: string }>()
  if (!threadId) return null
  return <ChatThreadView threadId={threadId} />
}

function ChatThreadView({ threadId }: { threadId: string }) {
  const transport = useMemo(() => createChatTransport(threadId), [threadId])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const { messages, sendMessage, status, error, setMessages } = useChat({
    id: threadId,
    transport,
  })

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)

    getThreadMessages(threadId)
      .then((history) => {
        if (!cancelled) setMessages(history)
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(err instanceof ApiError ? err.message : 'Failed to load conversation')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [threadId, setMessages])

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-destructive">
        {loadError}
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <MessageList messages={messages} awaitingReply={status === 'submitted'} />
      {error && <p className="px-4 pb-2 text-sm text-destructive">{error.message}</p>}
      <ChatInput disabled={status !== 'ready'} onSend={(text) => void sendMessage({ text })} />
    </div>
  )
}
