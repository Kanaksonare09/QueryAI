import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120_000,
})

// ── Chat ──────────────────────────────────────────────────────────────────
export const sendMessage = (payload) =>
  api.post('/chat/message', payload).then(r => r.data)

// ── Documents ─────────────────────────────────────────────────────────────
export const listDocuments = () =>
  api.get('/documents/').then(r => r.data)

export const uploadDocument = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/documents/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: e => onProgress && onProgress(Math.round(e.loaded * 100 / e.total)),
  }).then(r => r.data)
}

export const deleteDocument = (docId) =>
  api.delete(`/documents/${docId}`).then(r => r.data)

// ── Conversations ─────────────────────────────────────────────────────────
export const listConversations = () =>
  api.get('/conversations/').then(r => r.data)

export const getConversation = (id) =>
  api.get(`/conversations/${id}`).then(r => r.data)

export const deleteConversation = (id) =>
  api.delete(`/conversations/${id}`).then(r => r.data)

// ── System ────────────────────────────────────────────────────────────────
export const getSystemStatus = () =>
  api.get('/system/status').then(r => r.data)

export const getDbSchema = () =>
  api.get('/database/schema').then(r => r.data)

export const listModels = () =>
  api.get('/system/models').then(r => r.data)

export const switchModel = (model_name) =>
  // ModelConfig schema expects { model: string }
  api.post('/system/models/switch', { model: model_name }).then(r => r.data)

export default api
