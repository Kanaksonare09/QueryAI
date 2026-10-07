import { useState, useCallback, useRef } from 'react'
import { sendMessage } from '../api/client'

export function useChat(conversationId) {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  const send = useCallback(async (text, collectionId = null) => {
    if (!text.trim() || isLoading) return

    const userMsg = {
      id: Date.now(),
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)
    setError(null)

    try {
      const payload = {
        message: text,
        conversation_id: conversationId || undefined,
        collection_id: collectionId || undefined,
        include_sql: true,
        include_charts: true,
      }
      const data = await sendMessage(payload)

      const assistantMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.answer,
        sources: data.citations || [],   // ChatResponse returns 'citations'
        sqlQuery: data.sql_results?.sql_executed,
        sqlResults: data.sql_results,
        chartData: data.chart_data,
        chartType: data.chart_type || 'bar',
        toolsUsed: data.tools_used || [],
        intent: data.intent,
        processingTimeMs: data.processing_time_ms,
        timestamp: new Date().toISOString(),
        conversationId: data.conversation_id,
        confidenceScore: data.confidence_score,
        queryPlan: data.query_plan,
        clarificationOptions: data.clarification_options,
        optimizationSuggestions: data.optimization_suggestions,
        investigation: data.investigation,
      }
      setMessages(prev => [...prev, assistantMsg])
      return assistantMsg
    } catch (err) {
      const errMsg = err?.response?.data?.detail || err.message || 'Unknown error'
      setError(errMsg)
      setMessages(prev => [...prev, {
        id: Date.now() + 2,
        role: 'error',
        content: errMsg,
        timestamp: new Date().toISOString(),
      }])
    } finally {
      setIsLoading(false)
    }
  }, [conversationId, isLoading])

  const clear = useCallback(() => {
    setMessages([])
    setError(null)
  }, [])

  return { messages, isLoading, error, send, clear }
}
