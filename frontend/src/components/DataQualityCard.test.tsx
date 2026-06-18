import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DataQualityCard from './DataQualityCard'

describe('DataQualityCard', () => {
  it('renders 3 quality indicators with values', () => {
    render(
      <DataQualityCard
        veracityScore={0.92}
        timelinessScore={0.81}
        dataAsOf="2026-06-18"
      />
    )
    expect(screen.getByText('数据质量')).toBeInTheDocument()
    expect(screen.getByText('真实性评分')).toBeInTheDocument()
    expect(screen.getByText('时效性评分')).toBeInTheDocument()
    expect(screen.getByText('数据截止日期')).toBeInTheDocument()
    expect(screen.getByText('2026-06-18')).toBeInTheDocument()
  })

  it('renders dash placeholders when no data', () => {
    render(<DataQualityCard />)
    expect(screen.getAllByText('-').length).toBeGreaterThan(0)
  })
})
