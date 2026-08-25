import { describe, test, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { Toaster } from 'sonner'
import EnhanceButton from '@/components/EnhanceButton'
import { server } from '@/test/server'

function renderEnhanceButton(props = {}) {
  return render(
    <div>
      <EnhanceButton {...props} />
      <Toaster />
    </div>,
  )
}

describe('EnhanceButton', () => {
  test('calls onEnhanced with response text', async () => {
    server.use(
      http.post('*/api/enhance-prompt', () =>
        HttpResponse.json({ enhanced: 'better words here' })),
    )
    const onEnhanced = vi.fn()
    renderEnhanceButton({ text: 'draft', onEnhanced })
    fireEvent.click(screen.getByRole('button', { name: /enhance/i }))
    await waitFor(() => expect(onEnhanced).toHaveBeenCalledWith('better words here'))
  })

  test('shows error toast and does not call onEnhanced on failure', async () => {
    server.use(
      http.post('*/api/enhance-prompt', () =>
        HttpResponse.json({ error: 'unavailable' }, { status: 503 })),
    )
    const onEnhanced = vi.fn()
    renderEnhanceButton({ text: 'draft', onEnhanced })
    fireEvent.click(screen.getByRole('button', { name: /enhance/i }))
    await waitFor(() => expect(screen.getByRole('button')).toBeEnabled())
    expect(onEnhanced).not.toHaveBeenCalled()
  })

  test('is disabled when text is empty or whitespace', () => {
    renderEnhanceButton({ text: '   ', onEnhanced: vi.fn() })
    expect(screen.getByRole('button', { name: /enhance/i })).toBeDisabled()
  })
})
