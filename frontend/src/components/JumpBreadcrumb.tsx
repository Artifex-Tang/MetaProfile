import type { ReactNode } from 'react'
import { Breadcrumb } from 'antd'
import { useNavigate } from 'react-router-dom'
import { relLabel } from './RelationGraph'
import type { JumpCtx } from '../utils/crossProfile'

/**
 * 跳转上下文面包屑。返回入口与"来源实体"项合二为一（不另设独立按钮）。
 * ctx 来自路由 state（完整）或 ?from=（仅来源类型/id）；无来源时不渲染。
 */
export default function JumpBreadcrumb({ ctx }: { ctx: JumpCtx | null }) {
  const navigate = useNavigate()
  if (!ctx || !ctx.fromType || !ctx.fromId) return null

  const items: { title: ReactNode }[] = [
    {
      title: (
        <a
          onClick={() => navigate(`/${ctx.fromType}/${encodeURIComponent(ctx.fromId)}`)}
          style={{ cursor: 'pointer' }}
        >
          {ctx.fromName ?? ctx.fromId}
        </a>
      ),
    },
  ]
  if (ctx.relationType) {
    items.push({ title: `经「${relLabel(ctx.relationType)}」` })
  }

  return <Breadcrumb style={{ marginBottom: 12 }} items={items} />
}
