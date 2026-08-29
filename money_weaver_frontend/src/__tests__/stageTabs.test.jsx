import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import StageTabs from '@/components/studio/StageTabs'

describe('StageTabs', () => {
  it('visits only stages <= furthest unlocked', () => {
    const onGo = vi.fn()
    render(<StageTabs current={2} furthest={3} onGo={onGo} />)
    fireEvent.click(screen.getByRole('tab', { name: /storyboard/i }))
    expect(onGo).toHaveBeenCalledWith(3)
    fireEvent.click(screen.getByRole('tab', { name: /review/i }))
    expect(onGo).toHaveBeenCalledTimes(1)
  })

  it('marks the current stage as selected', () => {
    render(<StageTabs current={2} furthest={3} onGo={() => {}} />)
    expect(screen.getByRole('tab', { name: /script/i })).toHaveAttribute('aria-selected', 'true')
  })

  it('disables locked stages', () => {
    render(<StageTabs current={1} furthest={1} onGo={() => {}} />)
    expect(screen.getByRole('tab', { name: /review/i })).toBeDisabled()
  })
})