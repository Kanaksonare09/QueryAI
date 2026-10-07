import React, { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'
import {
  Send, Bot, User, Database, FileText, ChevronDown, ChevronUp,
  AlertCircle, Loader2, Sparkles, Code2, BarChart2, ShieldCheck, Zap, Search
} from 'lucide-react'
import './ChatWindow.css'

// ── Colour palette for charts ─────────────────────────────────────────────
const CHART_COLORS = ['#7c3aed','#06b6d4','#10b981','#f59e0b','#ef4444','#8b5cf6','#0ea5e9']

// ── Source badge ──────────────────────────────────────────────────────────
function SourceBadge({ source }) {
  const isDoc = source.type === 'document'
  return (
    <span className="source-badge" data-type={source.type}>
      {isDoc ? <FileText size={11}/> : <Database size={11}/>}
      <span>{source.filename || source.table || 'Source'}</span>
      {source.page && <span className="source-page">p.{source.page}</span>}
    </span>
  )
}

function InvestigationBlock({ inv }) {
  if (!inv) return null;

  if (inv.status === 'ERROR') {
    return (
      <div className="investigation-block error">
        <div className="inv-header">
          <Search size={16} /> <span>Root-Cause Investigation Failed</span>
        </div>
        <p className="inv-error-message">
          <AlertCircle size={14} style={{ display: 'inline', marginRight: '4px' }} />
          {inv.error_message || "Investigation failed."}
        </p>
      </div>
    )
  }

  return (
    <div className="investigation-block">
      <div className="inv-header">
        <Search size={16} /> <span>Root-Cause Investigation</span>
      </div>
      <div className="inv-baseline">
        <strong>Baseline Summary:</strong>
        <p>{inv.baseline_summary}</p>
      </div>
      <div className="inv-candidates">
        <strong>Root Cause Candidates:</strong>
        {inv.candidates.map((c, i) => (
          <div key={i} className="candidate-row">
            <div className="candidate-info">
              <span className="candidate-name">{c.driver_name}</span>
              <span className={`candidate-conf conf-${c.confidence.toLowerCase()}`}>{c.confidence} Confidence</span>
            </div>
            <div className="candidate-bar-wrap">
              <div className="candidate-bar" style={{ width: `${Math.min(100, Math.max(5, c.contribution_percent))}%` }} />
              <span className="candidate-pct">{c.contribution_percent}%</span>
            </div>
            <p className="candidate-exp">{c.explanation}</p>
          </div>
        ))}
      </div>
      <div className="inv-insight">
        <strong>💡 Final Insight:</strong>
        <p>{inv.final_insight}</p>
      </div>
      <div className="inv-evidence">
        <strong>Evidence Queries Used:</strong>
        <ul>
          {inv.evidence?.map((ev, i) => (
            <li key={i}><code>{ev.dimension}</code> breakdown executed</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function QueryDetailsBlock({ msg }) {
  const [open, setOpen] = useState(false)
  if (!msg.sqlQuery && !msg.queryPlan) return null
  
  return (
    <div className="sql-block">
      <button className="sql-toggle" onClick={() => setOpen(v=>!v)}>
        <Code2 size={14}/>
        <span>Query Details & SQL</span>
        {msg.confidenceScore && (
          <span className={`confidence-badge ${msg.confidenceScore > 80 ? 'high' : 'medium'}`}>
            <ShieldCheck size={12}/> {msg.confidenceScore}% Confidence
          </span>
        )}
        {open ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
      </button>
      {open && (
        <div className="sql-content">
          {msg.queryPlan && (
            <div className="query-plan">
              <strong>Intent:</strong> {msg.queryPlan.intent} | <strong>Metric:</strong> {msg.queryPlan.metric || 'N/A'}
            </div>
          )}
          {msg.sqlQuery && (
            <SyntaxHighlighter language="sql" style={oneDark} customStyle={{borderRadius:'8px',fontSize:'0.78rem',margin:'8px 0'}}>
              {msg.sqlQuery}
            </SyntaxHighlighter>
          )}
          {msg.optimizationSuggestions?.length > 0 && (
            <div className="optimization-suggestions">
              <strong><Zap size={12}/> Optimization:</strong>
              <ul>
                {msg.optimizationSuggestions.map((s,i)=><li key={i}>{s}</li>)}
              </ul>
            </div>
          )}
          {msg.sqlResults?.rows?.length > 0 && (
            <div className="sql-results">
              <table>
                <thead>
                  <tr>{msg.sqlResults.columns.map(c=><th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {msg.sqlResults.rows.slice(0,10).map((row,i)=>(
                    <tr key={i}>{msg.sqlResults.columns.map(c=><td key={c}>{String(row[c]??'')}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              {msg.sqlResults.rows.length > 10 && (
                <p className="sql-overflow">… and {msg.sqlResults.rows.length - 10} more rows</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Chart renderer ────────────────────────────────────────────────────────
function ChartBlock({ chartData, chartType }) {
  if (!chartData || chartData.length === 0) return null
  const keys = Object.keys(chartData[0]).filter(k => k !== 'name' && k !== 'label')

  return (
    <div className="chart-block">
      <div className="chart-header"><BarChart2 size={14}/><span>Visualization</span></div>
      <ResponsiveContainer width="100%" height={240}>
        {chartType === 'pie' ? (
          <PieChart>
            <Pie data={chartData} dataKey={keys[0]} nameKey="name" cx="50%" cy="50%" outerRadius={90} label>
              {chartData.map((_,i)=><Cell key={i} fill={CHART_COLORS[i%CHART_COLORS.length]}/>)}
            </Pie>
            <Tooltip contentStyle={{background:'#1e2130',border:'1px solid #7c3aed22',borderRadius:'8px',color:'#f1f5f9'}}/>
            <Legend/>
          </PieChart>
        ) : chartType === 'line' ? (
          <LineChart data={chartData} margin={{top:5,right:20,bottom:5,left:0}}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2130"/>
            <XAxis dataKey="name" stroke="#475569" tick={{fill:'#94a3b8',fontSize:11}}/>
            <YAxis stroke="#475569" tick={{fill:'#94a3b8',fontSize:11}}/>
            <Tooltip contentStyle={{background:'#1e2130',border:'1px solid #7c3aed22',borderRadius:'8px',color:'#f1f5f9'}}/>
            <Legend/>
            {keys.map((k,i)=><Line key={k} type="monotone" dataKey={k} stroke={CHART_COLORS[i%CHART_COLORS.length]} strokeWidth={2} dot={false}/>)}
          </LineChart>
        ) : (
          <BarChart data={chartData} margin={{top:5,right:20,bottom:5,left:0}}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e2130"/>
            <XAxis dataKey="name" stroke="#475569" tick={{fill:'#94a3b8',fontSize:11}}/>
            <YAxis stroke="#475569" tick={{fill:'#94a3b8',fontSize:11}}/>
            <Tooltip contentStyle={{background:'#1e2130',border:'1px solid #7c3aed22',borderRadius:'8px',color:'#f1f5f9'}}/>
            <Legend/>
            {keys.map((k,i)=><Bar key={k} dataKey={k} fill={CHART_COLORS[i%CHART_COLORS.length]} radius={[4,4,0,0]}/>)}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}

function MessageBubble({ msg, onSend }) {
  const isUser    = msg.role === 'user'
  const isError   = msg.role === 'error'
  const isAssistant = msg.role === 'assistant'

  return (
    <div className={`message-wrap ${msg.role}`}>
      <div className="message-avatar">
        {isUser    && <User size={16}/>}
        {isAssistant && <Bot size={16}/>}
        {isError   && <AlertCircle size={16}/>}
      </div>
      <div className="message-body">
        <div className="message-bubble">
          {isUser || isError ? (
            <p>{msg.content}</p>
          ) : (
            <>
              <ReactMarkdown
                components={{
                  code({node, inline, className, children, ...props}) {
                    const lang = /language-(\w+)/.exec(className||'')?.[1]
                    return !inline && lang ? (
                      <SyntaxHighlighter language={lang} style={oneDark}
                        customStyle={{borderRadius:'8px',fontSize:'0.78rem',margin:'8px 0'}} {...props}>
                        {String(children).replace(/\n$/,'')}
                      </SyntaxHighlighter>
                    ) : <code className={className} {...props}>{children}</code>
                  }
                }}
              >
                {msg.content}
              </ReactMarkdown>
              
              {msg.clarificationOptions && (
                <div className="clarification-options">
                  {msg.clarificationOptions.map((opt, i) => (
                    <button 
                      key={i} 
                      className="clarification-btn"
                      onClick={() => onSend(opt.value)}
                    >
                      <strong>{opt.label}</strong>
                      {opt.description && <span>{opt.description}</span>}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {isAssistant && !msg.clarificationOptions && (
          <>
            {msg.investigation ? (
              <InvestigationBlock inv={msg.investigation} />
            ) : (
              <>
                <ChartBlock chartData={msg.chartData} chartType={msg.chartType}/>
                <QueryDetailsBlock msg={msg} />
              </>
            )}

            {msg.sources?.length > 0 && (
              <div className="sources-row">
                <span className="sources-label">Sources:</span>
                {msg.sources.map((s,i)=><SourceBadge key={i} source={s}/>)}
              </div>
            )}
          </>
        )}

        <span className="message-time">
          {new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}
        </span>
      </div>
    </div>
  )
}

// ── Typing indicator ──────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="message-wrap assistant">
      <div className="message-avatar"><Bot size={16}/></div>
      <div className="message-body">
        <div className="message-bubble typing">
          <span/><span/><span/>
        </div>
      </div>
    </div>
  )
}

// ── Suggested prompts ─────────────────────────────────────────────────────
const SUGGESTIONS = [
  'What was the total revenue in Q4 2024?',
  'Compare revenue between top 3 regions as a chart',
  'Summarize the customer retention strategy from documents',
  'Which products have the highest churn risk?',
  'Show monthly revenue trend for 2024 vs 2025',
]

// ── Main ChatWindow ───────────────────────────────────────────────────────
export default function ChatWindow({ messages, isLoading, onSend }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const handleSubmit = (e) => {
    e?.preventDefault()
    if (!input.trim() || isLoading) return
    onSend(input)
    setInput('')
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() }
  }

  const isEmpty = messages.length === 0

  return (
    <div className="chat-window">
      {/* Messages */}
      <div className="messages-scroll">
        {isEmpty && !isLoading && (
          <div className="empty-state">
            <div className="empty-icon"><Sparkles size={32}/></div>
            <h2>What would you like to explore?</h2>
            <p>Ask anything about your documents or database. I can reason across both simultaneously.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s,i) => (
                <button key={i} className="suggestion-chip" onClick={() => { setInput(s); textareaRef.current?.focus() }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => <MessageBubble key={msg.id} msg={msg} onSend={onSend}/>)}
        {isLoading && <TypingIndicator/>}
        <div ref={bottomRef}/>
      </div>

      {/* Input */}
      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          id="chat-input"
          className="chat-textarea"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about your documents or database…"
          rows={1}
          disabled={isLoading}
          aria-label="Chat input"
        />
        <button
          type="submit"
          id="send-button"
          className="send-btn"
          disabled={!input.trim() || isLoading}
          aria-label="Send message"
        >
          {isLoading ? <Loader2 size={18} className="spin"/> : <Send size={18}/>}
        </button>
      </form>
    </div>
  )
}
