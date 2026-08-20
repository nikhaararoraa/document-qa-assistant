import { Outlet } from 'react-router-dom'

import { ThreadSidebar } from '@/components/chat/ThreadSidebar'

export function ChatLayout() {
  return (
    <div className="flex h-svh">
      <ThreadSidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </div>
    </div>
  )
}
