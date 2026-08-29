import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { it, expect, vi } from 'vitest'
import PremiseStage from '@/components/studio/PremiseStage'
import ApiService from '@/services/api'

const BASE = {
  premise: { text: '', durationSec: 60, nicheId: '', sequenceProjectId: null },
}

it('suggest fills premise text from random idea', async () => {
  vi.spyOn(ApiService, 'randomIdea').mockResolvedValue({
    title: 'Cats',
    topic: 'A cat learns to code',
    script: '',
  })
  const patch = vi.fn()
  render(<PremiseStage state={BASE} patch={patch} />)
  fireEvent.click(screen.getByRole('button', { name: /AI suggest/i }))
  await waitFor(() => expect(patch).toHaveBeenCalled())
  expect(patch.mock.calls[0][0].premise.text).toBe('A cat learns to code')
})

it('discover topics feeds premise via click', async () => {
  vi.spyOn(ApiService, 'fetchTopics').mockResolvedValue({
    topics: [{ title: 'AI gardens', source: 'hn', url: '' }],
  })
  const patch = vi.fn()
  render(
    <PremiseStage
      state={{ ...BASE, premise: { ...BASE.premise, nicheId: 'technology' } }}
      patch={patch}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: /AI discover/i }))
  fireEvent.click(await screen.findByText('AI gardens'))
  expect(patch.mock.calls.at(-1)[0].premise.text).toBe('AI gardens')
})

it('exposes duration select with spec values', () => {
  render(<PremiseStage state={BASE} patch={() => {}} />)
  expect(screen.getByRole('option', { name: '30 seconds' })).toBeInTheDocument()
  expect(screen.getByRole('option', { name: '5 minutes' })).toBeInTheDocument()
})

it('typing in premise textarea patches text', () => {
  const patch = vi.fn()
  render(<PremiseStage state={BASE} patch={patch} />)
  fireEvent.change(screen.getByLabelText(/premise/i), { target: { value: 'hello' } })
  expect(patch).toHaveBeenCalledWith({ premise: expect.objectContaining({ text: 'hello' }) })
})