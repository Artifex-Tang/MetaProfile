import { useEffect, useRef } from 'react'
import G6, { Graph } from '@antv/g6'
import { Space, Tag } from 'antd'
import { TYPE_META, metaOf, relLabel } from '../utils/relationMeta'

/** 关系项（与各画像 RelationList 的 item 结构一致） */
export interface RelItem {
  target_entity_id: string
  target_entity_type?: string | null
  target_name?: string | null
  relation_type?: string | null
  confidence?: number | null
  evidence?: string | null
}

/** 关系类型 → 中文展示（向后兼容：RelationGraph.test.tsx 仍从 './RelationGraph' 引入）。 */
export { relLabel }

export default function RelationGraph({
  relations,
  selfLabel = '当前实体',
  selfColor = '#ff4d4f',
  height = 360,
  onNodeClick,
  navTypes,
}: {
  relations: RelItem[]
  selfLabel?: string
  selfColor?: string
  height?: number
  /** 节点点击回调（仅 navTypes 命中的可跳节点触发）。 */
  onNodeClick?: (item: {
    id: string
    type?: string | null
    name?: string | null
    relationType?: string | null
    confidence?: number | null
    evidence?: string | null
  }) => void
  /** 可跳类型集合（小写）。决定哪些节点响应点击/hover；缺省=全部可点。 */
  navTypes?: Set<string>
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || relations.length === 0) return
    const container = ref.current
    const width = container.clientWidth || 560

    const selfNode = {
      id: '_self',
      label: selfLabel,
      type: 'modelRect',
      size: [90, 36],
      style: { fill: selfColor, stroke: selfColor, lineWidth: 0 },
      labelCfg: { style: { fill: '#fff', fontWeight: 700, fontSize: 13 } },
    }

    const nodes = relations.map(r => {
      const m = metaOf(r.target_entity_type)
      const conf = typeof r.confidence === 'number' ? r.confidence : 0.7
      const nav = navTypes ? navTypes.has((r.target_entity_type ?? '').toLowerCase()) : true
      return {
        id: r.target_entity_id,
        entityType: r.target_entity_type,   // 供 tooltip 与点击判定使用
        relationType: r.relation_type,
        confidence: r.confidence,
        evidence: r.evidence,
        name: r.target_name,
        label: r.target_name ?? r.target_entity_id.slice(0, 8),
        type: 'circle',
        size: 24 + conf * 26,
        style: { fill: m.color, stroke: '#fff', lineWidth: 2, cursor: nav ? 'pointer' : 'default' },
        labelCfg: { position: 'bottom', style: { fontSize: 11, fill: '#333' } },
      }
    })

    const edges = relations.map((r, i) => ({
      id: `e${i}`,
      source: '_self',
      target: r.target_entity_id,
      label: relLabel(r.relation_type),
      type: 'quadratic',
      style: { stroke: '#c5cad1', lineWidth: 1.6, endArrow: { path: G6.Arrow.triangle(7, 8, 0), fill: '#8c8c8c' } },
      labelCfg: { refY: 4, style: { fontSize: 10, fill: '#595959', background: { fill: '#ffffff', padding: [1, 4, 1, 4], radius: 3 } } },
    }))

    const tooltip = new G6.Tooltip({
      offsetX: 12,
      offsetY: 12,
      itemTypes: ['node', 'edge'],
      getContent: (e: any) => {
        const model = e.item?.getModel?.() ?? {}
        const out = document.createElement('div')
        if (e.itemType === 'node') {
          const id = String(model.id ?? '')
          if (id === '_self') {
            out.innerHTML = `<div style="padding:4px 6px">${selfLabel}</div>`
          } else {
            const m = metaOf(String(model.entityType ?? ''))
            out.innerHTML = `<div style="padding:4px 6px;min-width:90px">
              <b>${model.label ?? ''}</b><br/><span style="color:#888">${m.label}</span></div>`
          }
        } else {
          out.innerHTML = `<div style="padding:4px 6px">${model.label ?? ''}</div>`
        }
        return out
      },
    })

    const minimap = new G6.Minimap({ size: [100, 80], className: 'g6-minimap' })

    const graph = new Graph({
      container,
      width,
      height,
      fitView: true,
      fitViewPadding: 30,
      plugins: [tooltip, minimap],
      layout: {
        type: 'force',
        preventOverlap: true,
        nodeSpacing: 28,
        linkDistance: 150,
        nodeStrength: -120,
        edgeStrength: 0.7,
        collideStrength: 0.8,
        alpha: 0.9,
      },
      modes: {
        default: ['drag-canvas', 'zoom-canvas', 'drag-node', 'activate-relations'],
      },
      defaultNode: { type: 'circle', size: 36 },
      defaultEdge: { type: 'quadratic' },
      nodeStateStyles: {
        hover: { stroke: '#1677ff', lineWidth: 3, shadowBlur: 6, shadowColor: '#1677ff' },
      },
    })
    graph.data({ nodes: [selfNode, ...nodes], edges })
    graph.render()

    const isClickable = (model: any): boolean => {
      if (!model || model.id === '_self') return false
      const t = String(model.entityType ?? '')
      return navTypes ? navTypes.has(t.toLowerCase()) : true
    }

    const onClick = (e: any) => {
      const model = e.item?.getModel?.()
      if (!isClickable(model) || !onNodeClick) return
      onNodeClick({
        id: String(model.id),
        type: model.entityType,
        name: model.name,
        relationType: model.relationType,
        confidence: model.confidence,
        evidence: model.evidence,
      })
    }
    const onEnter = (e: any) => {
      const model = e.item?.getModel?.()
      if (!isClickable(model)) return
      graph.setItemState(e.item, 'hover', true)
    }
    const onLeave = (e: any) => graph.setItemState(e.item, 'hover', false)

    graph.on('node:click', onClick)
    graph.on('node:mouseenter', onEnter)
    graph.on('node:mouseleave', onLeave)
    return () => {
      graph.off('node:click', onClick)
      graph.off('node:mouseenter', onEnter)
      graph.off('node:mouseleave', onLeave)
      graph.destroy()
    }
  }, [relations, selfLabel, selfColor, height])

  return (
    <div>
      <Space size={6} style={{ marginBottom: 8, flexWrap: 'wrap' }}>
        <Tag color={selfColor}>{selfLabel}</Tag>
        {Object.entries(TYPE_META).map(([k, m]) => (
          <Tag key={k} color={m.color}>{m.label}</Tag>
        ))}
      </Space>
      {relations.length === 0 ? (
        <div style={{ height, lineHeight: `${height}px`, textAlign: 'center', color: '#999', background: '#fafafa', borderRadius: 4 }}>
          暂无关联数据
        </div>
      ) : (
        <div ref={ref} style={{ width: '100%', height, background: '#fafafa', borderRadius: 4 }} />
      )}
    </div>
  )
}
