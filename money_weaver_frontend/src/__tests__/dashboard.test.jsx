import { render, screen, fireEvent } from '@testing-library/react'
import { it, expect, vi, beforeEach } from 'vitest'
import Dashboard from '@/components/Dashboard'
import ApiService from '@/services/api'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => (p) => window.__nav(p) }
})

beforeEach(() => {
  window.__nav = vi.fn()
})

it('lists projects with resume-in-Studio for drafts', async () => {
  vi.spyOn(ApiService, 'getProjects').mockResolvedValue([
    { id: 1, title: 'Old', status: 'completed', workflow_type: 'assembler' },
    { id: 2, title: 'Draft', status: 'draft', workflow_type: 'assembler' },
  ])
  render(<Dashboard />)
  await screen.findByText('Draft')
  const resumeBtn = await screen.findByRole('button', { name: /resume/i })
  fireEvent.click(resumeBtn)
  expect(window.__nav).toHaveBeenCalledWith('/studio/2')
})

it('single New project CTA goes to /studio', async () => {
  vi.spyOn(ApiService, 'getProjects').mockResolvedValue([])
  render(<Dashboard />)
  await screen.findByRole('button', { name: /new project/i })
  fireEvent.click(screen.getByRole('button', { name: /new project/i }))
  expect(window.__nav).toHaveBeenCalledWith('/studio')
})

it('open goes to project detail', async () => {
  vi.spyOn(ApiService, 'getProjects').mockResolvedValue([
    { id: 3, title: 'Done', status: 'completed', workflow_type: 'generative' },
  ])
  render(<Dashboard />)
  await screen.findByText('Done')
  fireEvent.click(screen.getByRole('button', { name: /open/i }))
  expect(window.__nav).toHaveBeenCalledWith('/projects/3')
})