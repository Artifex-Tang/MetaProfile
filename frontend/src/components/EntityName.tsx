import { Tooltip, Button } from 'antd'
import { displayName, isUntranslated, type NameLike } from '../utils/displayName'

/**
 * 实体名展示（#9 非中文兜底）。
 * - name_cn 空 & name_en 有 → 显 name_en + Tooltip「原文 + 点翻译」+ 「译」按钮。
 * - 否则只显 displayName（name_cn 或 id）。
 */
export default function EntityName({
  entity, onTranslate, translating,
}: {
  entity: NameLike
  onTranslate?: () => void
  translating?: boolean
}) {
  const name = displayName(entity)
  if (!isUntranslated(entity) || !onTranslate) {
    return <span>{name}</span>
  }
  return (
    <Tooltip title={`原文: ${entity.name_en}（点翻译）`}>
      <span style={{ marginRight: 4 }}>{name}</span>
      <Button size="small" type="link" loading={translating} onClick={onTranslate}>译</Button>
    </Tooltip>
  )
}
