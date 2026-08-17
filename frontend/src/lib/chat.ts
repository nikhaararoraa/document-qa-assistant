import type { UIMessage } from 'ai'

import { api } from '@/lib/api'

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export function listThreads(): Promise<ChatThread[]> {
  return api.get<ChatThread[]>('/chat/threads')
}

export function createThread(): Promise<ChatThread> {
  // `title` is optional server-side, but the body itself is a required JSON
  // payload — `{}` is the "no title yet" request.
  return api.post<ChatThread>('/chat/threads', {})
}

export function getThreadMessages(threadId: string): Promise<UIMessage[]> {
  return api.get<UIMessage[]>(`/chat/threads/${threadId}/messages`)
}
