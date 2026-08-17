import { DefaultChatTransport } from 'ai'

import { env } from '@/lib/env'
import { authHeader } from '@/lib/http'

// `ai` / `@ai-sdk/react` API surface verified against the installed versions
// (ai@7.0.66, @ai-sdk/react@4.0.69) in node_modules/ai/dist/index.d.ts.
//
// The backend takes the thread id from the URL path
// (`POST /chat/threads/{thread_id}/stream`), not the request body, so the
// transport is built per-thread rather than pointed at one shared endpoint.
export function createChatTransport(threadId: string) {
  return new DefaultChatTransport({
    api: `${env.apiBaseUrl}/chat/threads/${threadId}/stream`,
    headers: authHeader,
  })
}
