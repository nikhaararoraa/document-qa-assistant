import type { UIMessage } from 'ai'

import { cn } from '@/lib/utils'

function textFromParts(message: UIMessage): string {
  return message.parts
    .filter((part) => part.type === 'text')
    .map((part) => part.text)
    .join('')
}

export function MessageBubble({ message }: { message: UIMessage }) {
  const isUser = message.role === 'user'
  const text = textFromParts(message)

  return (
    <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
      <div
        className={cn(
          'max-w-[75%] rounded-xl px-3.5 py-2 text-sm whitespace-pre-wrap',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground',
        )}
      >
        {text || <span className="text-muted-foreground">…</span>}
      </div>
    </div>
  )
}
