import React, { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar.jsx'
import ChatWindow from './components/ChatWindow.jsx'
import SchemaExplorer from './components/SchemaExplorer.jsx'
import { useChat } from './hooks/useChat.js'
import { useSystemStatus } from './hooks/useSystemStatus.js'
import { listDocuments } from './api/client.js'
import './App.css'

export default function App() {
  const [documents, setDocuments] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const { status } = useSystemStatus()
  const { messages, isLoading, send, clear } = useChat(conversationId)

  // Load docs on mount
  useEffect(() => {
    listDocuments()
      .then(data => setDocuments(Array.isArray(data) ? data : data.documents || []))
      .catch(console.error)
  }, [])

  const [currentView, setCurrentView] = useState('chat') // 'chat' or 'schema'

  const handleNewChat = () => {
    clear()
    setConversationId(null)
    setCurrentView('chat')
  }

  const handleSend = async (text) => {
    const reply = await send(text)
    if (reply?.conversationId && !conversationId) {
      setConversationId(reply.conversationId)
    }
  }

  return (
    <div className="app-layout">
      <Sidebar
        documents={documents}
        onDocumentsChange={setDocuments}
        systemStatus={status}
        onNewChat={handleNewChat}
        currentView={currentView}
        onViewChange={setCurrentView}
      />
      <main className="app-main">
        {currentView === 'chat' && (
          <ChatWindow
            messages={messages}
            isLoading={isLoading}
            onSend={handleSend}
          />
        )}
        {currentView === 'schema' && (
          <SchemaExplorer />
        )}
      </main>
    </div>
  )
}
