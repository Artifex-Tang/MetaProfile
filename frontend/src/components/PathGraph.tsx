import { useEffect, useRef } from 'react'
import G6, { Graph } from '@antv/g6'
import { Space, Tag } from 'antd'
import { TYPE_META, metaOf, relLabel } from '../utils/relationMeta'

export interface PGNode {
  id: string
  type?: string | null
  name?: string | null
}
export interface PGEdge {
  source: string
  target: string
  label?: string | null
}

export default function PathGraph({
  nodes,
  edges,
  onNodeClick,
  navTypes,
  emptyText = '暂无数据',
  height = 380,
  layout = 'tree',
}: {
  nodes: PGNode[]
  edges: PGEdge[]
  onNodeClick?: (n: PGNode) => void
  navTypes?: Set<string>
  emptyText?: string
  height?: number
  layout?: 'chain' | 'tree'
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || nodes.length === 0) return
    const container = ref.current
    const width = container.clientWidth || 640

    const gNodes = nodes.map(n => {
      const m = metaOf(n.type)
      const nav = navTypes ? navTypes.has((n.type ?? '').toLowerCase()) : true
      const name = n.name ?? String(n.id).slice(0, 8)
      return {
        id: n.id,
        entityType: n.type,
        name,
        label: name,
        type: 'circle',
        size: 34,
        style: { fill: m.color, stroke: '#fff', lineWidth: 2, cursor: nav ? 'pointer' : 'default' },
        labelCfg: { position: 'bottom', style: { fontSize: 11, fill: '#333' } },
      }
    })
    const seen = new Set<string>()
    const gEdges = edges
      .filter(e => {
        const k = `${e.source}->${e.target}`
        if (seen.has(k)) return false
        seen.add(k)
        return true
      })
      .map((e, i) => ({
        id: `e${i}`,
        source: e.source,
        target: e.target,
        label: relLabel(e.label),
        style: {
          stroke: '#c5cad1',
          lineWidth: 1.6,
          endArrow: { path: G6.Arrow.triangle(7, 8, 0), fill: '#8c8c8c' },
        },
      }))

    const tooltip = new G6.Tooltip({
      offsetX: 12,
      offsetY: 12,
      itemTypes: ['node', 'edge'],
      getContent: (e: any) => {
        const model = e.item?.getModel?.() ?? {}
        const el = document.createElement('div')
        if (e.itemType === 'node') {
          const m = metaOf(String(model.entityType ?? ''))
          el.innerHTML = `<div style="padding:4px 6px"><b>${model.label ?? ''}</b><br/><span style="color:#888">${m.label}</span></div>`
        } else {
          el.innerHTML = `<div style="padding:4px 6px">${model.label ?? ''}</div>`
        }
        return el
      },
    })

    const graph = new Graph({
      container,
      width,
      height,
      fitView: true,
      fitViewPadding: 30,
      plugins: [tooltip, new G6.Minimap({ size: [100, 80], className: 'g6-minimap' })],
      layout:
        layout === 'chain'
          ? { type: 'dagre', rankdir: 'LR', nodesep: 30, ranksep: 60 }
          : { type: 'dagre', rankdir: 'TB', nodesep: 40, ranksep: 50 },
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
      defaultNode: { type: 'circle', size: 34 },
      defaultEdge: { type: 'line' },
    })
    graph.data({ nodes: gNodes, edges: gEdges })
    graph.render()

    const onClick = (e: any) => {
      const model = e.item?.getModel?.()
      if (!model || !onNodeClick) return
      const t = String(model.entityType ?? '')
      if (navTypes && !navTypes.has(t.toLowerCase())) return
      onNodeClick({ id: String(model.id), type: model.entityType, name: model.name })
    }
    graph.on('node:click', onClick)
    return () => {
      graph.off('node:click', onClick)
      graph.destroy()
    }
  }, [nodes, edges, height, layout, navTypes, onNodeClick])

  const types = new Set(nodes.map(n => (n.type ?? '').toLowerCase()))
  return (
    <div>
      <Space size={6} style={{ marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(TYPE_META)
          .filter(([k]) => types.has(k))
          .map(([k, m]) => (
            <Tag key={k} color={m.color}>
              {m.label}
            </Tag>
          ))}
      </Space>
      {nodes.length === 0 ? (
        <div
          style={{
            height,
            lineHeight: `${height}px`,
            textAlign: 'center',
            color: '#999',
            background: '#fafafa',
            borderRadius: 4,
          }}
        >
          {emptyText}
        </div>
      ) : (
        <div ref={ref} style={{ width: '100%', height, background: '#fafafa', borderRadius: 4 }} />
      )}
    </div>
  )
}
