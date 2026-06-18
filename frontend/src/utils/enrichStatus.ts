/** enrich 补全任务状态中文标签 + 终态判定（4 画像详情按钮轮询共用）。 */

export function enrichStatusLabel(s?: string): string {
  switch (s) {
    case 'queued': return '排队中'
    case 'pending': return '执行中'
    case 'done': return '已完成'
    case 'skipped': return '无需补全'
    case 'failed': return '失败'
    case 'error': return '出错'
    case 'no_fill': return '无字段可补'
    default: return '未知'
  }
}

export function isEnrichTerminal(s?: string): boolean {
  return ['done', 'skipped', 'failed', 'error', 'no_fill'].includes(s ?? '')
}
