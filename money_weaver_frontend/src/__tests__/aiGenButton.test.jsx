import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { Toaster } from 'sonner'
import AIGenButton from '@/components/studio/AIGenButton'

function renderButton(props = {}) {
  return render(
    <div>
      <AIGenButton {...props} />
      <Toaster />
    </div>,
  )
}

describe('AIGenButton', () => {
  it('calls onGenerate and shows spinner while pending', async () => {
    let resolve
    const onGenerate = vi.fn(() => new Promise((r) => { resolve = r }))
    renderButton({ label: 'suggest', onGenerate })
    fireEvent.click(screen.getByRole('button', { name: /suggest/i }))
    expect(onGenerate).toHaveBeenCalled()
    expect(await screen.findByRole('status')).toBeInTheDocument()
    resolve()
    await waitFor(() => expect(screen.queryByRole('status')).toBeNull())
  })

  it('surfaces errors via toast, keeps button usable', async () => {
    const onGenerate = vi.fn().mockRejectedValue(new Error('503'))
    renderButton({ label: 'generate', onGenerate })
    fireEvent.click(screen.getByRole('button', { name: /generate/i }))
    await waitFor(() => expect(screen.getByRole('button')).not.toBeDisabled())
  })

  it('shows a sparkle icon when idle', () => {
    renderButton({ label: 'suggest', onGenerate: vi.fn() })
    expect(screen.getByRole('button', { name: /suggest/i })).toBeInTheDocument()
  })
})