import React, { useState, useEffect, useCallback } from 'react'
import { ReactFlow, MiniMap, Controls, Background, useNodesState, useEdgesState, MarkerType } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { getDbSchema } from '../api/client'
import { Database, Search, Key, Link as LinkIcon, Loader2 } from 'lucide-react'
import './SchemaExplorer.css'

// Custom node for tables
const TableNode = ({ data }) => {
  return (
    <div className="schema-table-node">
      <div className="table-header">
        <Database size={14} />
        <span>{data.label}</span>
      </div>
      <div className="table-columns">
        {data.columns.map((col, i) => (
          <div key={i} className="column-row">
            <span className="col-name">
              {data.primaryKeys?.includes(col.name) && <Key size={10} className="pk-icon" />}
              {data.foreignKeys?.some(fk => fk.column === col.name) && <LinkIcon size={10} className="fk-icon" />}
              {col.name}
            </span>
            <span className="col-type">{col.type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const nodeTypes = {
  tableNode: TableNode,
}

export default function SchemaExplorer() {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    fetchSchema()
  }, [])

  const fetchSchema = async () => {
    try {
      const data = await getDbSchema()
      if (data && data.tables) {
        // API returns tables as array [{name, columns, primary_keys, foreign_keys, ...}]
        buildGraph(Array.isArray(data.tables) ? data.tables : Object.values(data.tables))
      }
    } catch (err) {
      console.error('Failed to fetch schema', err)
    } finally {
      setLoading(false)
    }
  }

  const buildGraph = (tables) => {
    const initialNodes = []
    const initialEdges = []

    let y = 0
    const rowLimit = 3
    let colIndex = 0
    
    tables.forEach((tmeta) => {
      const tableName = tmeta.name
      
      // Create Node
      initialNodes.push({
        id: tableName,
        type: 'tableNode',
        position: { x: colIndex * 360, y: y * 420 },
        data: { 
          label: tableName, 
          columns: tmeta.columns || [],
          primaryKeys: tmeta.primary_keys || [],
          foreignKeys: tmeta.foreign_keys || [],
        },
      })

      // Create Edges (Foreign Keys)
      ;(tmeta.foreign_keys || []).forEach((fk, i) => {
        initialEdges.push({
          id: `e-${tableName}-${fk.references_table}-${i}`,
          source: tableName,
          target: fk.references_table,
          animated: true,
          style: { stroke: '#7c3aed', strokeWidth: 1.5 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: '#7c3aed',
          },
        })
      })

      colIndex++
      if (colIndex >= rowLimit) {
        colIndex = 0
        y++
      }
    })

    setNodes(initialNodes)
    setEdges(initialEdges)
  }

  // Handle Search Filtering
  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => {
        const isMatch = searchTerm === '' || n.data.label.toLowerCase().includes(searchTerm.toLowerCase())
        return {
          ...n,
          style: { ...n.style, opacity: isMatch ? 1 : 0.2 },
        }
      })
    )
  }, [searchTerm, setNodes])

  if (loading) {
    return (
      <div className="schema-loading">
        <Loader2 size={32} className="spin" />
        <p>Loading database schema...</p>
      </div>
    )
  }

  return (
    <div className="schema-explorer-container">
      <div className="schema-toolbar">
        <h2>Database Schema</h2>
        <div className="schema-search">
          <Search size={16} />
          <input 
            type="text" 
            placeholder="Search tables..." 
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
          />
        </div>
      </div>
      
      <div className="schema-graph-wrapper">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-right"
        >
          <Background color="#334155" gap={16} />
          <Controls />
          <MiniMap 
            nodeColor="#7c3aed"
            maskColor="rgba(15, 23, 42, 0.7)"
            style={{ backgroundColor: '#1e293b' }}
          />
        </ReactFlow>
      </div>
    </div>
  )
}
