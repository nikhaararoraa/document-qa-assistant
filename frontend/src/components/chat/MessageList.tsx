import type { UIMessage } from 'ai'
import { useEffect, useRef } from 'react'

import { MessageBubble } from '@/components/chat/MessageBubble'
import { StreamingIndicator } from '@/components/chat/StreamingIndicator'
import { ScrollArea } from '@/components/ui/scroll-area'

export function MessageList({
  messages,
  awaitingReply,
}: {
  messages: UIMessage[]
  awaitingReply: boolean
}) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, awaitingReply])

  return (
    <ScrollArea className="min-h-0 flex-1">
      <div className="flex flex-col gap-3 p-4">
        {messages.length === 0 && !awaitingReply && (
          <p className="text-center text-sm text-muted-foreground">
            Ask a question about the filings in the corpus to get started.
          </p>
        )}
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {awaitingReply && <StreamingIndicator />}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
