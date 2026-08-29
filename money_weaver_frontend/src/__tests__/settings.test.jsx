import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SettingsPage from '@/components/SettingsPage'
import ApiService from '@/services/api'
import { useAuthStore } from '@/store/authStore'

function renderSettings() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>,
  )
}

vi.mock('@/hooks/useModels', () => ({
  useModels: () => ({ data: { models: [{ id: 'm1', label: 'M1' }] } }),
}))
vi.mock('@/components/ModelPicker', () => ({
  default: ({ value, onChange, kinds }) => (
    <select
      aria-label={kinds.join(',')}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value || null)}
    >
      <option value="">Auto</option>
      <option value="m1">M1</option>
    </select>
  ),
}))

beforeEach(() => {
  vi.restoreAllMocks()
  useAuthStore.setState({ user: { id: 1 } })
})

it('renders exactly two sections', async () => {
  vi.spyOn(ApiService, 'getApiKeys').mockResolvedValue({ api_keys: [] })
  vi.spyOn(ApiService, 'getModelAssignments').mockResolvedValue({ assignments: {} })
  renderSettings()
  await screen.findByRole('heading', { name: /api keys/i })
  await screen.findByRole('heading', { name: /model assignments/i })
  expect(screen.queryByText(/profile/i)).toBeNull()
})

it('assignment PUT fires on change', async () => {
  vi.spyOn(ApiService, 'getApiKeys').mockResolvedValue({ api_keys: [] })
  vi.spyOn(ApiService, 'getModelAssignments').mockResolvedValue({ assignments: { script: null } })
  const put = vi.spyOn(ApiService, 'updateModelAssignments').mockResolvedValue({})
  renderSettings()
  await screen.findByText(/model assignments/i)
  fireEvent.change(screen.getAllByRole('combobox', { name: 'text' })[0], { target: { value: 'm1' } })
  await waitFor(() => expect(put).toHaveBeenCalledWith({ assignments: { idea: 'm1' } }))
})

it('lists saved API keys', async () => {
  vi.spyOn(ApiService, 'getApiKeys').mockResolvedValue({
    api_keys: [{ id: 7, name: 'Prod', provider: 'openrouter' }],
  })
  vi.spyOn(ApiService, 'getModelAssignments').mockResolvedValue({ assignments: {} })
  renderSettings()
  expect(await screen.findByText('Prod')).toBeInTheDocument()
  expect(screen.getAllByText('openrouter').length).toBeGreaterThan(0)
})