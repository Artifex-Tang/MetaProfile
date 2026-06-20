import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Radio, Space, InputNumber, Button } from 'antd'
import { useQuery } from '@tanstack/react-query'
import EntityTypeSelect, { EntitySel } from '../../components/EntityTypeSelect'
import PathGraph, { PGNode, PGEdge } from '../../components/PathGraph'
import { relationApi } from '../../api/relation'
import type { Viewpoint, RelationPathStep } from '../../api/types'

const NAV = new Set(['tech', 'org', 'person', 'project'])

export default function RelationExplore() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'path' | 'tech'>('path')
  // 模式1
  const [from, setFrom] = useState<EntitySel | null>(null)
  const [to, setTo] = useState<EntitySel | null>(null)
  const [depth, setDepth] = useState(3)
  const [queryPath, setQueryPath] = useState(0)
  // 模式2
  const [tech, setTech] = useState<EntitySel | null>(null)
  const [viewpoint, setViewpoint] = useState<Viewpoint>('evolve')
  const [queryTech, setQueryTech] = useState(0)

  const pathQ = useQuery({
    queryKey: ['rel-path', queryPath, from, to, depth],
    queryFn: async () => {
      if (!from || !to) return null
      return relationApi.getPath(from.type, from.id, to.id, depth)
    },
    enabled: queryPath > 0 && !!from && !!to,
  })

  const techQ = useQuery({
    queryKey: ['rel-tech', queryTech, tech?.id, viewpoint, depth],
    queryFn: async () => {
      if (!tech) return null
      return relationApi.getTechRelation(tech.id, viewpoint, depth)
    },
    enabled: queryTech > 0 && !!tech,
  })

  const jump = (n: PGNode) => {
    const t = (n.type ?? '').toLowerCase()
    if (NAV.has(t)) navigate(`/${t}/${n.id}`)
  }

  return (
    <Card title="关系探索">
      <Radio.Group
        value={mode}
        onChange={(e) => setMode(e.target.value)}
        style={{ marginBottom: 16 }}
      >
        <Radio.Button value="path">关系路径</Radio.Button>
        <Radio.Button value="tech">技术关系</Radio.Button>
      </Radio.Group>

      {mode === 'path' ? (
        <>
          <Space style={{ marginBottom: 12 }}>
            <EntityTypeSelect value={from} onChange={setFrom} placeholder="起点实体" />
            <EntityTypeSelect value={to} onChange={setTo} placeholder="终点实体" />
            <span>跳数</span>
            <InputNumber
              min={1}
              max={4}
              value={depth}
              onChange={(v) => setDepth(Number(v) || 3)}
            />
            <Button
              type="primary"
              disabled={!from || !to}
              onClick={() => setQueryPath((q) => q + 1)}
            >
              查询路径
            </Button>
          </Space>
          {pathQ.data && !pathQ.data.found && (
            <div style={{ color: '#999' }}>两实体间未发现路径（可增大跳数）</div>
          )}
          {pathQ.data?.found && (
            <PathGraph
              nodes={uniqNodes(pathQ.data.paths)}
              edges={pathEdges(pathQ.data.paths)}
              onNodeClick={jump}
              navTypes={NAV}
              layout="chain"
              emptyText="无路径"
            />
          )}
        </>
      ) : (
        <>
          <Space style={{ marginBottom: 12 }}>
            <EntityTypeSelect
              value={tech}
              onChange={setTech}
              allowedTypes={['tech']}
              placeholder="选择技术"
            />
            <Radio.Group
              value={viewpoint}
              onChange={(e) => setViewpoint(e.target.value)}
            >
              <Radio.Button value="evolve">演进链</Radio.Button>
              <Radio.Button value="prereq">前置树</Radio.Button>
            </Radio.Group>
            <span>深度</span>
            <InputNumber
              min={1}
              max={4}
              value={depth}
              onChange={(v) => setDepth(Number(v) || 4)}
            />
            <Button
              type="primary"
              disabled={!tech}
              onClick={() => setQueryTech((q) => q + 1)}
            >
              查询
            </Button>
          </Space>
          {techQ.data && techQ.data.nodes.length === 0 && (
            <div style={{ color: '#999' }}>
              {viewpoint === 'evolve' ? '该技术暂无演进记录' : '该技术暂无前置依赖'}
            </div>
          )}
          {techQ.data && techQ.data.nodes.length > 0 && (
            <PathGraph
              nodes={techQ.data.nodes.map((n) => ({
                id: n.entity_id,
                type: n.entity_type ?? undefined,
                name: n.name ?? undefined,
              }))}
              edges={techQ.data.edges.map((e) => ({
                source: e.source,
                target: e.target,
                label: e.rel_type,
              }))}
              onNodeClick={jump}
              navTypes={NAV}
              layout={viewpoint === 'evolve' ? 'chain' : 'tree'}
              emptyText={viewpoint === 'evolve' ? '暂无演进记录' : '暂无前置依赖'}
            />
          )}
        </>
      )}
    </Card>
  )
}

// helpers：路径结果(paths 是 RelationPathStep[][]) → PathGraph 的 nodes/edges
function uniqNodes(paths: RelationPathStep[][]): PGNode[] {
  const map = new Map<string, PGNode>()
  for (const s of paths.flat()) {
    const pairs: [string, string | null | undefined, string | null | undefined][] = [
      [s.from_id, s.from_type, s.from_name],
      [s.to_id, s.to_type, s.to_name],
    ]
    for (const [id, t, n] of pairs) {
      if (id && !map.has(id)) {
        map.set(id, { id, type: t ?? undefined, name: n ?? undefined })
      }
    }
  }
  return [...map.values()]
}

function pathEdges(paths: RelationPathStep[][]): PGEdge[] {
  return paths.flat().map((s) => ({
    source: s.from_id,
    target: s.to_id,
    label: s.relation,
  }))
}
