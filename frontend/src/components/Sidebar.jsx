import React, { useRef, useState } from 'react'
import { Upload, File, Trash2, CheckCircle, Clock, AlertCircle, RefreshCw, MessageSquare, Database as DatabaseIcon } from 'lucide-react'
import { uploadDocument, deleteDocument } from '../api/client'
import './Sidebar.css'

function DocItem({ doc, onDelete }) {
  const [deleting, setDeleting] = useState(false)

  const handleDelete = async () => {
    if (!confirm(`Delete "${doc.original_filename}"?`)) return
    setDeleting(true)
    try { await deleteDocument(doc.id); onDelete(doc.id) }
    catch { setDeleting(false) }
  }

  const statusIcon = {
    indexed: <CheckCircle size={13} className="status-icon indexed"/>,
    processing: <Clock size={13} className="status-icon processing"/>,
    failed: <AlertCircle size={13} className="status-icon failed"/>,
  }[doc.status] || <Clock size={13}/>

  return (
    <div className="doc-item">
      <File size={14} className="doc-file-icon"/>
      <div className="doc-info">
        <span className="doc-name" title={doc.original_filename}>{doc.original_filename}</span>
        <span className="doc-meta">
          {statusIcon}
          {doc.status}
          {doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
        </span>
      </div>
      <button className="doc-delete" onClick={handleDelete} disabled={deleting} aria-label="Delete document">
        {deleting ? <RefreshCw size={13} className="spin"/> : <Trash2 size={13}/>}
      </button>
    </div>
  )
}

export default function Sidebar({ documents, onDocumentsChange, systemStatus, onNewChat, currentView, onViewChange }) {
  const fileInputRef = useRef(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [dragOver, setDragOver] = useState(false)

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return
    setUploading(true)
    setUploadProgress(0)
    for (const file of Array.from(files)) {
      try {
        const doc = await uploadDocument(file, p => setUploadProgress(p))
        onDocumentsChange(prev => [doc, ...prev])
      } catch (err) {
        console.error('Upload failed', err)
      }
    }
    setUploading(false)
    setUploadProgress(0)
  }

  const onFileInput = e => handleFiles(e.target.files)
  const onDrop = e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }
  const onDragOver = e => { e.preventDefault(); setDragOver(true) }
  const onDragLeave = () => setDragOver(false)

  // system status dots
  const services = systemStatus ? [
    { name: 'Backend', ok: true },
    { name: 'Ollama',  ok: systemStatus.ollama_connected },
    { name: 'MySQL',   ok: systemStatus.mysql_connected },
    { name: 'ChromaDB',ok: systemStatus.chromadb_connected },
  ] : []

  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-orb"/>
          <div>
            <h1>AI Assistant</h1>
            <span>Offline Intelligence</span>
          </div>
        </div>
        <button id="new-chat-btn" className="new-chat-btn" onClick={onNewChat}>+ New Chat</button>
      </div>

      {/* Navigation */}
      <div className="sidebar-nav">
        <button 
          className={`nav-btn ${currentView === 'chat' ? 'active' : ''}`}
          onClick={() => onViewChange('chat')}
        >
          <MessageSquare size={16} /> Chat
        </button>
        <button 
          className={`nav-btn ${currentView === 'schema' ? 'active' : ''}`}
          onClick={() => onViewChange('schema')}
        >
          <DatabaseIcon size={16} /> Schema Explorer
        </button>
      </div>

      {/* System status */}
      {services.length > 0 && (
        <div className="sidebar-section">
          <p className="section-label">System Status</p>
          <div className="status-grid">
            {services.map(s => (
              <div key={s.name} className="status-pill" data-ok={s.ok}>
                <span className="status-dot"/>
                {s.name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload */}
      <div className="sidebar-section">
        <p className="section-label">Documents</p>
        <div
          id="upload-zone"
          className={`upload-zone ${dragOver ? 'drag-over' : ''} ${uploading ? 'uploading' : ''}`}
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => !uploading && fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          aria-label="Upload documents"
          onKeyDown={e => e.key==='Enter' && fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            hidden
            multiple
            accept=".pdf,.docx,.txt,.csv,.md,.json"
            onChange={onFileInput}
          />
          {uploading ? (
            <>
              <RefreshCw size={22} className="spin upload-icon"/>
              <span>{uploadProgress}%</span>
              <div className="progress-bar"><div className="progress-fill" style={{width:`${uploadProgress}%`}}/></div>
            </>
          ) : (
            <>
              <Upload size={22} className="upload-icon"/>
              <span>Drop files or click</span>
              <small>PDF · DOCX · TXT · CSV · MD</small>
            </>
          )}
        </div>

        {/* Doc list */}
        <div className="doc-list">
          {documents.length === 0 && (
            <p className="doc-empty">No documents indexed yet.</p>
          )}
          {documents.map(doc => (
            <DocItem key={doc.id} doc={doc} onDelete={id => onDocumentsChange(prev => prev.filter(d=>d.id!==id))}/>
          ))}
        </div>
      </div>

      {/* Model info */}
      {systemStatus?.current_model && (
        <div className="sidebar-footer">
          <span className="footer-label">Model</span>
          <span className="footer-value">{systemStatus.current_model}</span>
        </div>
      )}
    </aside>
  )
}
