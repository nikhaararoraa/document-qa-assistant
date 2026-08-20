import { Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from '@/components/ProtectedRoute'
import { ChatEmptyState } from '@/pages/chat/ChatEmptyState'
import { ChatLayout } from '@/pages/chat/ChatLayout'
import { ChatThread } from '@/pages/chat/ChatThread'
import { SignIn } from '@/pages/SignIn'
import { SignUp } from '@/pages/SignUp'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<SignIn />} />
      <Route path="/signup" element={<SignUp />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ChatLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<ChatEmptyState />} />
        <Route path="chat/:threadId" element={<ChatThread />} />
      </Route>
    </Routes>
  )
}

export default App
