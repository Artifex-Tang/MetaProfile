import { Card, Descriptions, Progress } from 'antd'

interface Props {
  veracityScore?: number
  timelinessScore?: number
  dataAsOf?: string
}

const toPercent = (v?: number): number | null =>
  v != null ? Math.round(v * 100) : null

const statusFor = (p: number): 'success' | 'normal' | 'exception' =>
  p >= 80 ? 'success' : p >= 50 ? 'normal' : 'exception'

/** 数据质量卡片：展示 ingest_ods scorer 产出的真实性/时效性评分与数据截止日期。 */
export default function DataQualityCard({ veracityScore, timelinessScore, dataAsOf }: Props) {
  const vp = toPercent(veracityScore)
  const tp = toPercent(timelinessScore)
  return (
    <Card size="small" title="数据质量" style={{ marginTop: 12 }}>
      <Descriptions column={1} size="small">
        <Descriptions.Item label="真实性评分">
          {vp != null ? (
            <Progress percent={vp} size="small" status={statusFor(vp)} />
          ) : (
            '-'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="时效性评分">
          {tp != null ? (
            <Progress percent={tp} size="small" status={statusFor(tp)} />
          ) : (
            '-'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="数据截止日期">
          {dataAsOf ?? '-'}
        </Descriptions.Item>
      </Descriptions>
    </Card>
  )
}
